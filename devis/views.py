# devis/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Devis, LigneDevis
from .forms import DevisForm, LigneDevisForm, LigneDevisFormSet
from .utils import generer_numero_devis, email_documents_configure, expliquer_erreur_email, MESSAGE_EMAIL_NON_CONFIGURE
from django.http import HttpResponse, Http404, JsonResponse
import os
import json
from django.conf import settings
from produits.models import Produit
from django.db.models import Q, Count
from django.urls import reverse
from django.utils import timezone
from django.core.mail import send_mail, get_connection, EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from taxes.models import Taxe


# ✅ Helper pour obtenir la configuration email depuis la base de données
def get_email_config(type_email='principal'):
    """Récupère la configuration email depuis la base de données"""
    try:
        from users.admin_models import ConfigurationEmail
        config = ConfigurationEmail.objects.get(type_email=type_email, actif=True)
        return config
    except Exception:
        return None


def get_email_connection(type_email='principal'):
    """Retourne une connexion SMTP basée sur la configuration en base"""
    config = get_email_config(type_email)
    if config:
        return get_connection(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            use_tls=config.use_tls,
            use_ssl=config.use_ssl,
        )
    # Fallback sur les settings
    return get_connection(
        host=getattr(settings, 'FACTURE_EMAIL_HOST', 'smtp.gmail.com'),
        port=getattr(settings, 'FACTURE_EMAIL_PORT', 587),
        username=getattr(settings, 'FACTURE_EMAIL_HOST_USER', ''),
        password=getattr(settings, 'FACTURE_EMAIL_HOST_PASSWORD', ''),
        use_tls=True,
    )


def get_from_email(type_email='principal'):
    """Retourne l'adresse d'expédition depuis la base ou les settings"""
    config = get_email_config(type_email)
    if config:
        return config.from_email
    return getattr(settings, 'FACTURE_DEFAULT_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL)


@login_required
def liste_devis(request):
    statut = request.GET.get('statut', '')
    recherche = request.GET.get('q', '')

    devis = Devis.objects.filter(utilisateur=request.user)

    if statut:
        devis = devis.filter(statut=statut)
    if recherche:
        devis = devis.filter(
            Q(numero__icontains=recherche) |
            Q(client__nom__icontains=recherche) |
            Q(client__entreprise__icontains=recherche)
        )

    nb_total = Devis.objects.filter(utilisateur=request.user).count()
    nb_attente = Devis.objects.filter(utilisateur=request.user, statut='en_attente').count()
    nb_acceptes = Devis.objects.filter(utilisateur=request.user, statut='accepte').count()
    nb_refuses = Devis.objects.filter(utilisateur=request.user, statut='refuse').count()

    return render(request, 'devis/liste_devis.html', {
        'devis': devis.select_related('client').order_by('-date_creation'),
        'statut': statut,
        'recherche': recherche,
        'nb_total': nb_total,
        'nb_attente': nb_attente,
        'nb_acceptes': nb_acceptes,
        'nb_refuses': nb_refuses,
    })


@login_required
def ajouter_devis(request):
    if request.method == 'POST':
        form = DevisForm(request.POST, user=request.user)
        formset = LigneDevisFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            # Validation de la date
            date_validite = form.cleaned_data.get('date_validite')
            if date_validite <= timezone.now().date():
                messages.error(request, 'La date de validité doit être postérieure à aujourd\'hui.')
                return render_creation_devis(request, form, formset)

            devis = form.save(commit=False)
            devis.utilisateur = request.user
            devis.numero = generer_numero_devis(request.user)
            
            # Générer les tokens pour l'approbation
            devis.generer_tokens()
            
            # ✅ RÉCUPÉRER LES TAXES PERSONNALISÉES (champ caché)
            taxes_perso = request.POST.get('taxes_personnalisees', '')
            if taxes_perso:
                try:
                    taxes_data = json.loads(taxes_perso)
                    devis.taxes_personnalisees = taxes_data
                except json.JSONDecodeError:
                    devis.taxes_personnalisees = {}
            else:
                devis.taxes_personnalisees = {}
            
            # ✅ IMPORTANT : Désactiver l'ancien système si des taxes personnalisées existent
            if devis.taxes_personnalisees and (devis.taxes_personnalisees.get('ids') or devis.taxes_personnalisees.get('personnalisees')):
                devis.taux_taxe = 0
                devis.type_taxe = ''
            else:
                devis.taux_taxe = form.cleaned_data.get('taux_taxe', 0)
                devis.type_taxe = form.cleaned_data.get('type_taxe', 'TVA')
            
            devis.save()
            
            # Sauvegarder les taxes sélectionnées (ManyToMany)
            if form.cleaned_data.get('taxes'):
                devis.taxes.set(form.cleaned_data['taxes'])

            # Sauvegarder les lignes
            lignes_sauvegardees = 0
            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.devis = devis
                    ligne.save()
                    lignes_sauvegardees += 1

            if lignes_sauvegardees == 0:
                devis.delete()
                messages.error(request, 'Veuillez ajouter au moins un produit ou service.')
                return render_creation_devis(request, form, formset)

            messages.success(request, f'Devis {devis.numero} créé avec succès !')
            
            # Rediriger vers la page de gestion des liens
            return redirect('gestion_liens_devis', pk=devis.pk)
        else:
            messages.error(request, 'Veuillez corriger les erreurs dans le formulaire.')
            print(f"ERREURS FORM: {form.errors}")
            print(f"ERREURS FORMSET: {formset.errors}")
    else:
        form = DevisForm(user=request.user)
        formset = LigneDevisFormSet(prefix='lignes', user=request.user)

    return render_creation_devis(request, form, formset)


def render_creation_devis(request, form, formset):
    """Helper pour le rendu de la création"""
    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays').order_by('nom')

    return render(request, 'devis/form_devis.html', {
        'form': form,
        'formset': formset,
        'produits': produits,
        'lignes_existantes': [],
        'titre': 'Créer un devis',
        'bouton': 'Créer le devis',
    })


@login_required
def gestion_liens_devis(request, pk):
    """Page pour gérer les liens d'approbation et client"""
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)

    # Documents anciens créés sans liens publics
    if not devis.token_client or not devis.token_approbation:
        devis.generer_tokens()
        devis.save(update_fields=['token_client', 'token_approbation'])
    
    base_url = request.build_absolute_uri('/')[:-1]
    lien_approbation = f"{base_url}{reverse('visualiser_devis_approbation', args=[devis.token_approbation])}"
    lien_client = f"{base_url}{reverse('visualiser_devis_client', args=[devis.token_client])}"
    
    return render(request, 'devis/gestion_liens.html', {
        'devis': devis,
        'lien_approbation': lien_approbation,
        'lien_client': lien_client,
    })


def visualiser_devis_approbation(request, token):
    """Page publique pour que le supérieur approuve le devis"""
    devis = get_object_or_404(Devis, token_approbation=token)

    # Une seule décision possible, tant que le devis est en attente
    if devis.statut != 'en_attente':
        if devis.statut == 'rejete_superieur':
            message = 'Ce devis a déjà été rejeté.'
        elif devis.statut == 'expire':
            message = 'Ce devis a expiré.'
        else:
            message = 'Ce devis a déjà été approuvé.'
        return render(request, 'devis/public/approbation.html', {
            'devis': devis,
            'deja_traite': True,
            'message_warning': message,
        })
    
    if request.method == 'POST':
        action = request.POST.get('action')
        commentaire = request.POST.get('commentaire', '')
        
        if action == 'approuver':
            devis.approuve_par = request.user if request.user.is_authenticated else None
            devis.approuve_le = timezone.now()
            devis.commentaire_approbation = commentaire
            devis.statut = 'approuve_superieur'
            devis.save()
            
            try:
                send_mail(
                    subject=f'Devis {devis.numero} approuvé',
                    message=f'Votre devis {devis.numero} a été approuvé.\n\nCommentaire : {commentaire}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[devis.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            return render(request, 'devis/public/approbation.html', {
                'devis': devis,
                'action_effectuee': 'approuver',
                'message_success': f'Devis {devis.numero} approuvé avec succès !',
                'commentaire': commentaire
            })
            
        elif action == 'rejeter':
            devis.statut = 'rejete_superieur'
            devis.approuve_le = timezone.now()
            devis.commentaire_approbation = commentaire
            devis.save()
            
            try:
                send_mail(
                    subject=f'Devis {devis.numero} rejeté',
                    message=f'Votre devis {devis.numero} a été rejeté.\n\nMotif : {commentaire}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[devis.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            return render(request, 'devis/public/approbation.html', {
                'devis': devis,
                'action_effectuee': 'rejeter',
                'message_success': f'Devis {devis.numero} rejeté.',
                'commentaire': commentaire
            })
    
    return render(request, 'devis/public/approbation.html', {
        'devis': devis,
        'deja_traite': False
    })


def visualiser_devis_client(request, token):
    """Page publique pour que le client accepte/refuse le devis"""
    devis = get_object_or_404(Devis, token_client=token)

    # Vérifier d'abord si le client a déjà répondu (le statut a changé depuis)
    if devis.accepte_par_client is not None:
        return render(request, 'devis/public/client.html', {
            'devis': devis,
            'deja_repondu': True,
            'message_warning': 'Vous avez déjà répondu à ce devis.'
        })

    if devis.statut == 'approuve_superieur' and devis.date_validite < timezone.now().date():
        devis.statut = 'expire'
        devis.save(update_fields=['statut'])

    if devis.statut == 'expire':
        return render(request, 'devis/public/client.html', {
            'devis': devis,
            'message_warning': 'Ce devis a expiré. Contactez votre interlocuteur pour en obtenir un nouveau.',
            'en_attente': True
        })

    if devis.statut != 'approuve_superieur':
        return render(request, 'devis/public/client.html', {
            'devis': devis,
            'message_warning': 'Ce devis n\'a pas encore été approuvé en interne.',
            'en_attente': True
        })
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accepter':
            devis.accepte_par_client = True
            devis.accepte_client_le = timezone.now()
            devis.statut = 'accepte'
            devis.save()
            
            try:
                send_mail(
                    subject=f'Devis {devis.numero} accepté',
                    message=f'Le client {devis.client.nom} a accepté le devis {devis.numero}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[devis.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            return render(request, 'devis/public/client.html', {
                'devis': devis,
                'action_effectuee': 'accepter',
                'message_success': f'Merci ! Votre acceptation a été enregistrée.'
            })
            
        elif action == 'refuser':
            devis.accepte_par_client = False
            devis.accepte_client_le = timezone.now()
            devis.statut = 'refuse'
            devis.save()
            
            try:
                send_mail(
                    subject=f'Devis {devis.numero} refusé',
                    message=f'Le client {devis.client.nom} a refusé le devis {devis.numero}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[devis.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            return render(request, 'devis/public/client.html', {
                'devis': devis,
                'action_effectuee': 'refuser',
                'message_success': f'Nous avons bien enregistré votre refus.'
            })
    
    return render(request, 'devis/public/client.html', {
        'devis': devis,
    })


@login_required
def detail_devis(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)
    lignes = devis.lignes.all().select_related('produit')
    
    if devis.date_validite < timezone.now().date() and devis.statut in ('en_attente', 'approuve_superieur'):
        devis.statut = 'expire'
        devis.save(update_fields=['statut'])

    return render(request, 'devis/detail_devis.html', {
        'devis': devis,
        'lignes': lignes,
    })


@login_required
def modifier_devis(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)

    if devis.transforme_en_facture:
        messages.error(request, 'Ce devis a déjà été transformé en facture.')
        return redirect('detail_devis', pk=pk)

    if request.method == 'POST':
        form = DevisForm(request.POST, user=request.user, instance=devis)
        formset = LigneDevisFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            date_validite = form.cleaned_data.get('date_validite')
            if date_validite <= timezone.now().date():
                messages.error(request, 'La date de validité doit être postérieure à aujourd\'hui.')
                return render_modification_devis(request, devis, form, formset)

            devis = form.save(commit=False)

            # Un devis rejeté ou expiré qui est corrigé repart en approbation
            if devis.statut in ('rejete_superieur', 'expire'):
                devis.statut = 'en_attente'
                devis.approuve_par = None
                devis.approuve_le = None

            # ✅ RÉCUPÉRER LES TAXES PERSONNALISÉES
            taxes_perso = request.POST.get('taxes_personnalisees', '')
            if taxes_perso:
                try:
                    taxes_data = json.loads(taxes_perso)
                    devis.taxes_personnalisees = taxes_data
                except json.JSONDecodeError:
                    devis.taxes_personnalisees = {}
            else:
                devis.taxes_personnalisees = {}
            
            # ✅ Désactiver l'ancien système si des taxes personnalisées existent
            if devis.taxes_personnalisees and (devis.taxes_personnalisees.get('ids') or devis.taxes_personnalisees.get('personnalisees')):
                devis.taux_taxe = 0
                devis.type_taxe = ''
            else:
                devis.taux_taxe = form.cleaned_data.get('taux_taxe', 0)
                devis.type_taxe = form.cleaned_data.get('type_taxe', 'TVA')
            
            devis.save()
            
            if form.cleaned_data.get('taxes'):
                devis.taxes.set(form.cleaned_data['taxes'])
            else:
                devis.taxes.clear()
            
            devis.lignes.all().delete()

            lignes_sauvegardees = 0
            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.devis = devis
                    ligne.save()
                    lignes_sauvegardees += 1

            if lignes_sauvegardees == 0:
                messages.error(request, 'Veuillez ajouter au moins un produit ou service.')
                return render_modification_devis(request, devis, form, formset)

            messages.success(request, f'Devis {devis.numero} modifié avec succès !')
            return redirect('detail_devis', pk=devis.pk)
        else:
            messages.error(request, 'Veuillez corriger les erreurs.')
        lignes_existantes = []
    else:
        form = DevisForm(user=request.user, instance=devis)
        formset = LigneDevisFormSet(prefix='lignes', user=request.user)
        lignes_existantes = list(devis.lignes.all().select_related('produit'))

    return render_modification_devis(request, devis, form, formset, lignes_existantes)


def render_modification_devis(request, devis, form, formset, lignes_existantes=None):
    if lignes_existantes is None:
        lignes_existantes = []
    
    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays').order_by('nom')

    return render(request, 'devis/form_devis.html', {
        'form': form,
        'formset': formset,
        'produits': produits,
        'lignes_existantes': lignes_existantes,
        'titre': f'Modifier - {devis.numero}',
        'bouton': 'Enregistrer',
        'devis': devis,
    })


@login_required
def supprimer_devis(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)

    if request.method == 'POST':
        numero = devis.numero
        devis.delete()
        messages.success(request, f'Devis {numero} supprimé.')
        return redirect('liste_devis')

    return render(request, 'devis/confirmer_suppression.html', {'devis': devis})


@login_required
def transformer_en_facture(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)

    if devis.statut != 'accepte':
        messages.error(request, 'Seul un devis accepté peut être transformé en facture.')
        return redirect('detail_devis', pk=pk)

    if devis.transforme_en_facture:
        messages.error(request, 'Ce devis a déjà été transformé en facture.')
        return redirect('detail_devis', pk=pk)

    if request.method == 'POST':
        from factures.models import Facture, LigneFacture
        from devis.utils import generer_numero_facture
        import datetime

        # La facture reprend EXACTEMENT les taxes du devis accepté par le client :
        # un devis sans taxe donne une facture sans taxe (pas de taux par défaut du pays).
        facture = Facture(
            utilisateur=request.user,
            client=devis.client,
            devis=devis,
            numero=generer_numero_facture(request.user),
            date_echeance=timezone.now().date() + datetime.timedelta(days=30),
            notes=devis.notes,
            # Le devis a déjà été approuvé en interne et accepté par le client :
            # la facture part directement en « non payée », avec ses propres liens publics.
            statut='non_payee',
            pays=devis.pays,
            type_taxe=devis.type_taxe if devis.taux_taxe else '',
            taux_taxe=devis.taux_taxe or 0,
            taxes_personnalisees=devis.taxes_personnalisees or {},
            devise_choisie=devis.devise_choisie,
            approuve_par=devis.approuve_par,
            approuve_le=devis.approuve_le,
            accepte_par_client=True,
            accepte_client_le=devis.accepte_client_le,
        )
        facture.generer_tokens()
        facture.save()
        
        facture.taxes.set(devis.taxes.all())

        for ligne in devis.lignes.all().select_related('produit'):
            LigneFacture.objects.create(
                facture=facture,
                description=ligne.description,
                quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire,
                tva=ligne.tva or 0,
            )

        devis.transforme_en_facture = True
        devis.save()

        messages.success(request, f'Facture {facture.numero} créée avec succès !')
        return redirect('detail_facture', pk=facture.pk)

    return render(request, 'devis/confirmer_transformation.html', {'devis': devis})


@login_required
def telecharger_pdf_devis(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)
    from .pdf import generer_pdf_devis

    buffer = generer_pdf_devis(devis)

    nom_fichier = f"devis_{devis.numero}.pdf"
    chemin_relatif = f"devis/pdf/{nom_fichier}"
    chemin_complet = os.path.join(settings.MEDIA_ROOT, chemin_relatif)

    os.makedirs(os.path.dirname(chemin_complet), exist_ok=True)

    with open(chemin_complet, 'wb') as f:
        f.write(buffer.getvalue())

    devis.fichier_pdf = chemin_relatif
    devis.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    return response


def telecharger_pdf_devis_public(request, token):
    """PDF du devis sans compte : accessible avec le jeton du lien client ou d'approbation."""
    devis = Devis.objects.filter(Q(token_client=token) | Q(token_approbation=token)).first()
    if devis is None:
        raise Http404
    from .pdf import generer_pdf_devis
    buffer = generer_pdf_devis(devis)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="devis_{devis.numero}.pdf"'
    return response


@login_required
def envoyer_devis_email(request, pk):
    """Envoie le devis par email au client ou à une autre personne"""
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)

    # Documents anciens créés sans liens publics
    if not devis.token_client or not devis.token_approbation:
        devis.generer_tokens()
        devis.save(update_fields=['token_client', 'token_approbation'])
    
    # Récupérer l'option choisie par l'utilisateur
    option_destinataire = request.POST.get('option_destinataire')
    
    # Déterminer l'adresse email du destinataire
    if option_destinataire == 'client':
        email_destinataire = devis.client.email
        if not email_destinataire:
            messages.error(request, f"Le client {devis.client.nom} n'a pas d'adresse email enregistrée.")
            return redirect('liste_devis')
    else:
        email_destinataire = request.POST.get('email_autre')
        if not email_destinataire:
            messages.error(request, "Veuillez saisir une adresse email.")
            return redirect('liste_devis')
    
    if not email_documents_configure():
        messages.error(request, MESSAGE_EMAIL_NON_CONFIGURE)
        return redirect('liste_devis')

    # Vérifier que le PDF existe, sinon le générer
    from .pdf import generer_pdf_devis
    buffer = generer_pdf_devis(devis)
    
    # Base URL pour les liens absolus
    base_url = request.build_absolute_uri('/')[:-1]
    
    # Contexte pour le template email
    context = {
        'devis': devis,
        'client': devis.client,
        'total_ht': devis.calculer_total_ht(),
        'total_ttc': devis.calculer_total_ttc(),
        'tva': devis.calculer_tva(),
        'devise': devis.get_devise(),
        'date_validite': devis.date_validite,
        'lien_devis': f"{base_url}{reverse('visualiser_devis_client', args=[devis.token_client])}",
        'lien_pdf': f"{base_url}{reverse('pdf_devis_public', args=[devis.token_client])}",
        'reponse_possible': devis.statut == 'approuve_superieur',
        'utilisateur': request.user,
        'taxes_details': devis.get_taxes_details(),
    }
    
    # Rendre le template HTML
    html_message = render_to_string('devis/emails/devis_email.html', context)
    plain_message = strip_tags(html_message)
    
    # ✅ Utiliser la configuration depuis la base de données
    sujet = f"Devis {devis.numero} - {devis.client.nom}"
    
    # Récupérer la connexion et l'expéditeur depuis la base de données
    # Note: les devis utilisent aussi le type 'factures' car ils sont envoyés par le même serveur
    connection = get_connection(
        host=getattr(settings, 'FACTURE_EMAIL_HOST', 'smtp.gmail.com'),
        port=getattr(settings, 'FACTURE_EMAIL_PORT', 587),
        username=getattr(settings, 'FACTURE_EMAIL_HOST_USER', ''),
        password=getattr(settings, 'FACTURE_EMAIL_HOST_PASSWORD', ''),
        use_tls=True,
    )
    
    # Essayer d'utiliser la configuration en base pour les factures
    config = get_email_config('factures')
    if config:
        connection = get_connection(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            use_tls=config.use_tls,
            use_ssl=config.use_ssl,
        )
        from_email = config.from_email
    else:
        from_email = getattr(settings, 'FACTURE_DEFAULT_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL)
    
    email = EmailMessage(
        subject=sujet,
        body=html_message,
        from_email=from_email,
        to=[email_destinataire],
        reply_to=[request.user.email],
        connection=connection,
    )
    email.content_subtype = 'html'
    
    # Ajouter le PDF en pièce jointe
    email.attach(f"devis_{devis.numero}.pdf", buffer.getvalue(), 'application/pdf')
    
    try:
        email.send()
        messages.success(request, f"Devis {devis.numero} envoyé par email à {email_destinataire}")
        if devis.statut == 'en_attente':
            messages.warning(request, "Ce devis n'est pas encore approuvé en interne : "
                                      "le client pourra y répondre une fois l'approbation donnée.")
    except Exception as e:
        messages.error(request, expliquer_erreur_email(e))
    
    return redirect('liste_devis')


# ══════════════════════════════════════════════════
# API : réponses reçues via les liens publics (rafraîchissement auto)
# ══════════════════════════════════════════════════

# Statuts où un supérieur ou le client peut encore répondre
DEVIS_EN_COURS = ('en_attente', 'approuve_superieur')
FACTURES_EN_COURS = ('en_attente', 'approuvee')


def _evenements_publics(type_doc, numero, avant, apres):
    """Décrit les réponses arrivées par les liens publics entre deux états (statut, accepte_par_client)."""
    statut_avant, client_avant = avant
    statut_apres, client_apres = apres
    evenements = []
    if type_doc == 'devis':
        if statut_avant == 'en_attente' and statut_apres in ('approuve_superieur', 'accepte', 'refuse'):
            evenements.append(f"Devis {numero} approuvé par le supérieur.")
        elif statut_avant == 'en_attente' and statut_apres == 'rejete_superieur':
            evenements.append(f"Devis {numero} rejeté par le supérieur.")
        libelle = 'Devis'
        accorde = ''
    else:
        # « approuvée » ou, si le client a déjà répondu dans l'intervalle, la suite du circuit
        if statut_avant == 'en_attente' and (statut_apres == 'approuvee' or client_apres is not None):
            evenements.append(f"Facture {numero} approuvée par le supérieur.")
        elif statut_avant == 'en_attente' and statut_apres == 'rejetee' and client_apres is None:
            evenements.append(f"Facture {numero} rejetée par le supérieur.")
        libelle = 'Facture'
        accorde = 'e'
    if client_avant is None and client_apres is True:
        evenements.append(f"{libelle} {numero} accepté{accorde} par le client.")
    elif client_avant is None and client_apres is False:
        evenements.append(f"{libelle} {numero} refusé{accorde} par le client.")
    return evenements


@login_required
def api_etat_documents(request):
    """
    Interrogée régulièrement par les pages de l'émetteur. Compare l'état des devis
    et factures en attente de réponse avec le dernier passage (gardé en session) :
    si un supérieur ou un client a répondu, ajoute une notification et demande au
    navigateur de recharger la page. Les actions de l'utilisateur lui-même
    (payée, annulée, modification...) ne déclenchent rien.
    """
    from factures.models import Facture

    precedent = request.session.get('etat_documents')
    actuel = {'devis': {}, 'factures': {}}
    evenements = []

    for cle, modele, en_cours in (('devis', Devis, DEVIS_EN_COURS), ('factures', Facture, FACTURES_EN_COURS)):
        anciens = (precedent or {}).get(cle, {})
        lignes = (modele.objects
                  .filter(utilisateur=request.user)
                  .filter(Q(statut__in=en_cours) | Q(pk__in=[int(pk) for pk in anciens]))
                  .values_list('pk', 'numero', 'statut', 'accepte_par_client'))
        for pk, numero, statut, accepte in lignes:
            if statut in en_cours:
                actuel[cle][str(pk)] = [statut, accepte]
            avant = anciens.get(str(pk))
            if avant and tuple(avant) != (statut, accepte):
                evenements += _evenements_publics('devis' if cle == 'devis' else 'facture',
                                                  numero, tuple(avant), (statut, accepte))

    request.session['etat_documents'] = actuel
    for texte in evenements:
        messages.success(request, texte)
    return JsonResponse({'changement': bool(evenements), 'evenements': evenements})


@login_required
def tableau_de_bord(request):
    from factures.models import Facture
    from clients.models import Client
    import json
    from datetime import date
    from dateutil.relativedelta import relativedelta

    nb_clients = Client.objects.filter(utilisateur=request.user).count()
    nb_devis = Devis.objects.filter(utilisateur=request.user).count()
    nb_devis_en_attente = Devis.objects.filter(utilisateur=request.user, statut='en_attente').count()
    nb_factures = Facture.objects.filter(utilisateur=request.user).count()
    nb_factures_payees = Facture.objects.filter(utilisateur=request.user, statut='payee').count()

    factures_payees = Facture.objects.filter(utilisateur=request.user, statut='payee')
    ca_total = sum(f.calculer_total_ttc() for f in factures_payees)
    factures_attente = Facture.objects.filter(utilisateur=request.user, statut='non_payee')
    montant_attente = sum(f.calculer_total_ttc() for f in factures_attente)

    derniers_devis = Devis.objects.filter(utilisateur=request.user).order_by('-date_creation')[:5]
    dernieres_factures = Facture.objects.filter(utilisateur=request.user).order_by('-date_creation')[:5]

    aujourd_hui = date.today()
    mois_labels, devis_par_mois, factures_par_mois = [], [], []
    for i in range(11, -1, -1):
        mois = aujourd_hui - relativedelta(months=i)
        mois_labels.append(mois.strftime('%b %Y'))
        devis_par_mois.append(
            Devis.objects.filter(
                utilisateur=request.user,
                date_creation__year=mois.year,
                date_creation__month=mois.month
            ).count()
        )
        factures_par_mois.append(
            Facture.objects.filter(
                utilisateur=request.user,
                date_creation__year=mois.year,
                date_creation__month=mois.month
            ).count()
        )

    ca_labels, ca_par_mois = [], []
    for i in range(5, -1, -1):
        mois = aujourd_hui - relativedelta(months=i)
        ca_labels.append(mois.strftime('%b %Y'))
        fs = Facture.objects.filter(
            utilisateur=request.user,
            statut='payee',
            date_creation__year=mois.year,
            date_creation__month=mois.month
        )
        ca_par_mois.append(float(sum(f.calculer_total_ttc() for f in fs)))

    # Tous les statuts, dans l'ordre du cycle de vie
    devis_par_statut = dict(
        Devis.objects.filter(utilisateur=request.user)
        .values_list('statut').annotate(n=Count('id'))
    )
    devis_statuts_labels = [label for _, label in Devis.STATUT_CHOICES]
    devis_statuts_data = [devis_par_statut.get(code, 0) for code, _ in Devis.STATUT_CHOICES]

    factures_par_statut = dict(
        Facture.objects.filter(utilisateur=request.user)
        .values_list('statut').annotate(n=Count('id'))
    )
    factures_statuts_labels = [label for _, label in Facture.STATUT_CHOICES]
    factures_statuts_data = [factures_par_statut.get(code, 0) for code, _ in Facture.STATUT_CHOICES]

    return render(request, 'tableau_de_bord.html', {
        'nb_clients': nb_clients,
        'nb_devis': nb_devis,
        'nb_devis_en_attente': nb_devis_en_attente,
        'nb_factures': nb_factures,
        'nb_factures_payees': nb_factures_payees,
        'ca_total': ca_total,
        'montant_attente': montant_attente,
        'derniers_devis': derniers_devis,
        'dernieres_factures': dernieres_factures,
        'mois_labels': json.dumps(mois_labels),
        'devis_par_mois': json.dumps(devis_par_mois),
        'factures_par_mois': json.dumps(factures_par_mois),
        'ca_labels': json.dumps(ca_labels),
        'ca_par_mois': json.dumps(ca_par_mois),
        'devis_statuts_labels': json.dumps(devis_statuts_labels),
        'devis_statuts_data': json.dumps(devis_statuts_data),
        'factures_statuts_labels': json.dumps(factures_statuts_labels),
        'factures_statuts_data': json.dumps(factures_statuts_data),
    })