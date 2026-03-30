# devis/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Devis, LigneDevis
from .forms import DevisForm, LigneDevisForm, LigneDevisFormSet
from .utils import generer_numero_devis
from django.http import HttpResponse
import os
from django.conf import settings
from produits.models import Produit
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.core.mail import send_mail
from taxes.models import Taxe


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
                messages.error(request, '❌ La date de validité doit être postérieure à aujourd\'hui.')
                return render_creation_devis(request, form, formset)

            devis = form.save(commit=False)
            devis.utilisateur = request.user
            devis.numero = generer_numero_devis(request.user)
            
            # Générer les tokens pour l'approbation
            devis.generer_tokens()
            
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
                messages.error(request, '❌ Veuillez ajouter au moins un produit ou service.')
                return render_creation_devis(request, form, formset)

            messages.success(request, f'✅ Devis {devis.numero} créé avec succès !')
            
            # Rediriger vers la page de gestion des liens
            return redirect('gestion_liens_devis', pk=devis.pk)
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs dans le formulaire.')
            print(f"❌ ERREURS FORM: {form.errors}")
            print(f"❌ ERREURS FORMSET: {formset.errors}")
    else:
        form = DevisForm(user=request.user)
        formset = LigneDevisFormSet(prefix='lignes', user=request.user)

    return render_creation_devis(request, form, formset)


def render_creation_devis(request, form, formset):
    """Helper pour le rendu de la création"""
    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

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
    
    # Construire les URLs
    base_url = request.build_absolute_uri('/')[:-1]
    lien_approbation = f"{base_url}{reverse('visualiser_devis_approbation', args=[devis.token_approbation])}"
    lien_client = f"{base_url}{reverse('visualiser_devis_client', args=[devis.token_client])}"
    
    return render(request, 'devis/gestion_liens.html', {
        'devis': devis,
        'lien_approbation': lien_approbation,
        'lien_client': lien_client,
    })


# ✅ CORRIGÉ : Avec popup de confirmation
def visualiser_devis_approbation(request, token):
    """Page publique pour que le supérieur approuve le devis"""
    devis = get_object_or_404(Devis, token_approbation=token)
    
    # Vérifier si déjà traité
    if devis.approuve_par:
        return render(request, 'devis/public/approbation.html', {
            'devis': devis,
            'deja_traite': True,
            'message_warning': 'Ce devis a déjà été approuvé.'
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
            
            # Envoyer notification au créateur
            try:
                send_mail(
                    subject=f'✅ Devis {devis.numero} approuvé',
                    message=f'Votre devis {devis.numero} a été approuvé.\n\nCommentaire : {commentaire}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[devis.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            # ✅ Afficher la page avec popup de succès
            return render(request, 'devis/public/approbation.html', {
                'devis': devis,
                'action_effectuee': 'approuver',
                'message_success': f'✅ Devis {devis.numero} approuvé avec succès !',
                'commentaire': commentaire
            })
            
        elif action == 'rejeter':
            devis.statut = 'rejete_superieur'
            devis.commentaire_approbation = commentaire
            devis.save()
            
            # Envoyer notification au créateur
            try:
                send_mail(
                    subject=f'❌ Devis {devis.numero} rejeté',
                    message=f'Votre devis {devis.numero} a été rejeté.\n\nMotif : {commentaire}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[devis.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            # ✅ Afficher la page avec popup de rejet
            return render(request, 'devis/public/approbation.html', {
                'devis': devis,
                'action_effectuee': 'rejeter',
                'message_success': f'❌ Devis {devis.numero} rejeté.',
                'commentaire': commentaire
            })
    
    return render(request, 'devis/public/approbation.html', {
        'devis': devis,
        'deja_traite': False
    })


def visualiser_devis_client(request, token):
    """Page publique pour que le client accepte/refuse le devis"""
    devis = get_object_or_404(Devis, token_client=token)
    
    # Vérifier si le devis est approuvé
    if devis.statut != 'approuve_superieur':
        return render(request, 'devis/public/client.html', {
            'devis': devis,
            'message_warning': 'Ce devis n\'a pas encore été approuvé en interne.',
            'en_attente': True
        })
    
    if devis.accepte_par_client is not None:
        return render(request, 'devis/public/client.html', {
            'devis': devis,
            'deja_repondu': True,
            'message_warning': 'Vous avez déjà répondu à ce devis.'
        })
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accepter':
            devis.accepte_par_client = True
            devis.accepte_client_le = timezone.now()
            devis.statut = 'accepte'
            devis.save()
            
            # Notifier le commercial
            try:
                send_mail(
                    subject=f'✅ Devis {devis.numero} accepté',
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
                'message_success': f'✅ Merci ! Votre acceptation a été enregistrée.'
            })
            
        elif action == 'refuser':
            devis.accepte_par_client = False
            devis.accepte_client_le = timezone.now()
            devis.statut = 'refuse'
            devis.save()
            
            # Notifier le commercial
            try:
                send_mail(
                    subject=f'❌ Devis {devis.numero} refusé',
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
                'message_success': f'ℹ️ Nous avons bien enregistré votre refus.'
            })
    
    return render(request, 'devis/public/client.html', {
        'devis': devis,
    })


@login_required
def detail_devis(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)
    lignes = devis.lignes.all().select_related('produit')
    
    # Vérifier si le devis est expiré
    if devis.date_validite < timezone.now().date() and devis.statut == 'en_attente':
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
        messages.error(request, '❌ Ce devis a déjà été transformé en facture.')
        return redirect('detail_devis', pk=pk)

    if request.method == 'POST':
        form = DevisForm(request.POST, user=request.user, instance=devis)
        formset = LigneDevisFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            # Validation de la date
            date_validite = form.cleaned_data.get('date_validite')
            if date_validite <= timezone.now().date():
                messages.error(request, '❌ La date de validité doit être postérieure à aujourd\'hui.')
                return render_modification_devis(request, devis, form, formset)

            devis = form.save()
            
            # Sauvegarder les taxes sélectionnées (ManyToMany)
            if form.cleaned_data.get('taxes'):
                devis.taxes.set(form.cleaned_data['taxes'])
            else:
                devis.taxes.clear()
            
            # Supprimer les anciennes lignes
            devis.lignes.all().delete()

            # Créer les nouvelles lignes
            lignes_sauvegardees = 0
            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.devis = devis
                    ligne.save()
                    lignes_sauvegardees += 1

            if lignes_sauvegardees == 0:
                messages.error(request, '❌ Veuillez ajouter au moins un produit ou service.')
                return render_modification_devis(request, devis, form, formset)

            messages.success(request, f'✏️ Devis {devis.numero} modifié avec succès !')
            return redirect('detail_devis', pk=devis.pk)
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs.')
    else:
        form = DevisForm(user=request.user, instance=devis)
        formset = LigneDevisFormSet(prefix='lignes', user=request.user)
        lignes_existantes = list(devis.lignes.all().select_related('produit'))

    return render_modification_devis(request, devis, form, formset, lignes_existantes)


def render_modification_devis(request, devis, form, formset, lignes_existantes=None):
    """Helper pour le rendu de la modification"""
    if lignes_existantes is None:
        lignes_existantes = []
    
    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

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
        messages.success(request, f'🗑️ Devis {numero} supprimé.')
        return redirect('liste_devis')

    return render(request, 'devis/confirmer_suppression.html', {'devis': devis})


@login_required
def transformer_en_facture(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)

    if devis.statut != 'accepte':
        messages.error(request, '❌ Seul un devis accepté peut être transformé en facture.')
        return redirect('detail_devis', pk=pk)

    if devis.transforme_en_facture:
        messages.error(request, '❌ Ce devis a déjà été transformé en facture.')
        return redirect('detail_devis', pk=pk)

    if request.method == 'POST':
        from factures.models import Facture, LigneFacture
        from devis.utils import generer_numero_facture
        import datetime

        client = devis.client
        pays_facture = devis.pays or getattr(client, 'pays_nom', '')
        type_taxe_facture = devis.type_taxe or getattr(client, 'type_taxe_nom', 'TVA')
        taux_taxe_facture = devis.taux_taxe or getattr(client, 'taux_tva', 0)

        facture = Facture.objects.create(
            utilisateur=request.user,
            client=client,
            devis=devis,
            numero=generer_numero_facture(request.user),
            date_echeance=timezone.now().date() + datetime.timedelta(days=30),
            notes=devis.notes,
            statut='non_payee',
            pays=pays_facture,
            type_taxe=type_taxe_facture,
            taux_taxe=taux_taxe_facture,
        )
        
        # Copier les taxes du devis vers la facture
        if devis.taxes.exists():
            facture.taxes.set(devis.taxes.all())

        for ligne in devis.lignes.all().select_related('produit'):
            LigneFacture.objects.create(
                facture=facture,
                description=ligne.description,
                quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire,
                tva=ligne.tva,
            )

        devis.transforme_en_facture = True
        devis.save()

        messages.success(request, f'✅ Facture {facture.numero} créée avec succès !')
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

    devis_statuts_labels = ['En attente', 'Acceptés', 'Refusés']
    devis_statuts_data = [
        Devis.objects.filter(utilisateur=request.user, statut='en_attente').count(),
        Devis.objects.filter(utilisateur=request.user, statut='accepte').count(),
        Devis.objects.filter(utilisateur=request.user, statut='refuse').count(),
    ]
    factures_statuts_labels = ['Non payées', 'Payées', 'Annulées']
    factures_statuts_data = [
        Facture.objects.filter(utilisateur=request.user, statut='non_payee').count(),
        Facture.objects.filter(utilisateur=request.user, statut='payee').count(),
        Facture.objects.filter(utilisateur=request.user, statut='annulee').count(),
    ]

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