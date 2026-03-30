from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms as django_forms
from .models import Facture, LigneFacture 
from .forms import FactureForm, LigneFactureForm, LigneFactureFormSet, BaseLigneFactureFormSet
from produits.models import Produit
from devis.utils import generer_numero_facture
from django.http import HttpResponse
import os
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.core.mail import send_mail


@login_required
def liste_factures(request):
    statut = request.GET.get('statut', '')
    recherche = request.GET.get('q', '')

    factures = Facture.objects.filter(utilisateur=request.user)

    if statut:
        factures = factures.filter(statut=statut)
    if recherche:
        factures = factures.filter(numero__icontains=recherche) | \
                   factures.filter(client__nom__icontains=recherche)

    return render(request, 'factures/liste_factures.html', {
        'factures': factures,
        'statut': statut,
        'recherche': recherche,
        'nb_total': Facture.objects.filter(utilisateur=request.user).count(),
        'nb_non_payees': Facture.objects.filter(utilisateur=request.user, statut='non_payee').count(),
        'nb_payees': Facture.objects.filter(utilisateur=request.user, statut='payee').count(),
        'nb_annulees': Facture.objects.filter(utilisateur=request.user, statut='annulee').count(),
    })


@login_required
def ajouter_facture(request):
    if request.method == 'POST':
        form = FactureForm(request.user, request.POST)
        formset = LigneFactureFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            facture = form.save(commit=False)
            facture.utilisateur = request.user
            facture.numero = generer_numero_facture(request.user)
            
            # ✅ Générer les tokens pour l'approbation
            facture.generer_tokens()
            
            facture.save()

            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.facture = facture
                    ligne.save()

            messages.success(request, f'✅ Facture {facture.numero} créée !')
            
            # ✅ Rediriger vers la page de gestion des liens
            return redirect('gestion_liens_facture', pk=facture.pk)
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs.')
    else:
        form = FactureForm(request.user)
        formset = LigneFactureFormSet(prefix='lignes', user=request.user)

    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

    return render(request, 'factures/form_facture.html', {
        'form': form,
        'formset': formset,
        'produits': produits,
        'lignes_existantes': [],
        'titre': 'Créer une facture',
        'bouton': 'Créer la facture'
    })


@login_required
def gestion_liens_facture(request, pk):
    """Page pour gérer les liens d'approbation et client"""
    facture = get_object_or_404(Facture, pk=pk, utilisateur=request.user)
    
    # Construire les URLs
    base_url = request.build_absolute_uri('/')[:-1]
    lien_approbation = f"{base_url}{reverse('visualiser_facture_approbation', args=[facture.token_approbation])}"
    lien_client = f"{base_url}{reverse('visualiser_facture_client', args=[facture.token_client])}"
    
    return render(request, 'factures/gestion_liens.html', {
        'facture': facture,
        'lien_approbation': lien_approbation,
        'lien_client': lien_client,
    })


def visualiser_facture_approbation(request, token):
    """Page publique pour que le supérieur approuve la facture"""
    facture = get_object_or_404(Facture, token_approbation=token)
    
    # Vérifier si déjà traité
    if facture.approuve_par:
        messages.warning(request, "Cette facture a déjà été approuvée.")
        return render(request, 'factures/public/deja_traite.html', {'facture': facture})
    
    if request.method == 'POST':
        action = request.POST.get('action')
        commentaire = request.POST.get('commentaire', '')
        
        if action == 'approuver':
            facture.approuve_par = request.user if request.user.is_authenticated else None
            facture.approuve_le = timezone.now()
            facture.commentaire_approbation = commentaire
            facture.statut = 'approuvee'
            facture.save()
            
            # Envoyer notification au créateur
            try:
                send_mail(
                    subject=f'✅ Facture {facture.numero} approuvée',
                    message=f'Votre facture {facture.numero} a été approuvée.\n\nCommentaire : {commentaire}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[facture.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            messages.success(request, "✅ Facture approuvée avec succès !")
            return redirect('visualiser_facture_approbation', token=token)
            
        elif action == 'rejeter':
            facture.statut = 'rejetee'
            facture.commentaire_approbation = commentaire
            facture.save()
            
            # Envoyer notification au créateur
            try:
                send_mail(
                    subject=f'❌ Facture {facture.numero} rejetée',
                    message=f'Votre facture {facture.numero} a été rejetée.\n\nMotif : {commentaire}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[facture.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            messages.info(request, "Facture rejetée.")
            return redirect('visualiser_facture_approbation', token=token)
    
    return render(request, 'factures/public/approbation.html', {
        'facture': facture,
    })


def visualiser_facture_client(request, token):
    """Page publique pour que le client accepte la facture"""
    facture = get_object_or_404(Facture, token_client=token)
    
    # Vérifier si la facture est approuvée
    if facture.statut != 'approuvee':
        messages.warning(request, "Cette facture n'a pas encore été approuvée en interne.")
        return render(request, 'factures/public/en_attente.html', {'facture': facture})
    
    if facture.accepte_par_client is not None:
        messages.warning(request, "Vous avez déjà répondu à cette facture.")
        return render(request, 'factures/public/deja_repondu.html', {'facture': facture})
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accepter':
            facture.accepte_par_client = True
            facture.accepte_client_le = timezone.now()
            facture.statut = 'non_payee'
            facture.save()
            
            # Notifier le commercial
            try:
                send_mail(
                    subject=f'✅ Facture {facture.numero} acceptée',
                    message=f'Le client {facture.client.nom} a accepté la facture {facture.numero}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[facture.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            messages.success(request, "✅ Merci ! Votre acceptation a été enregistrée.")
            return redirect('visualiser_facture_client', token=token)
            
        elif action == 'refuser':
            facture.accepte_par_client = False
            facture.accepte_client_le = timezone.now()
            facture.statut = 'rejetee'
            facture.save()
            
            # Notifier le commercial
            try:
                send_mail(
                    subject=f'❌ Facture {facture.numero} refusée',
                    message=f'Le client {facture.client.nom} a refusé la facture {facture.numero}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[facture.utilisateur.email],
                    fail_silently=True,
                )
            except:
                pass
            
            messages.info(request, "Nous avons bien enregistré votre refus.")
            return redirect('visualiser_facture_client', token=token)
    
    return render(request, 'factures/public/client.html', {
        'facture': facture,
    })


@login_required
def detail_facture(request, pk):
    facture = get_object_or_404(
        Facture.objects.select_related('client__pays_obj'),
        pk=pk, 
        utilisateur=request.user
    )
    lignes = facture.lignes.all()

    return render(request, 'factures/detail_facture.html', {
        'facture': facture,
        'lignes': lignes,
    })


@login_required
def modifier_facture(request, pk):
    facture = get_object_or_404(
        Facture.objects.select_related('client__pays_obj'),
        pk=pk, 
        utilisateur=request.user
    )

    if facture.statut == 'payee':
        messages.error(request, '❌ Une facture payée ne peut pas être modifiée.')
        return redirect('detail_facture', pk=pk)

    if request.method == 'POST':
        form = FactureForm(request.user, request.POST, instance=facture)
        formset = LigneFactureFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            form.save()
            facture.lignes.all().delete()

            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.facture = facture
                    ligne.save()

            messages.success(request, f'✏️ Facture {facture.numero} modifiée !')
            return redirect('detail_facture', pk=facture.pk)
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs.')
        lignes_existantes = []
    else:
        form = FactureForm(request.user, instance=facture)
        formset = LigneFactureFormSet(prefix='lignes', user=request.user)
        lignes_existantes = list(facture.lignes.all())

    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

    return render(request, 'factures/form_facture.html', {
        'form': form,
        'formset': formset,
        'produits': produits,
        'lignes_existantes': lignes_existantes,
        'titre': f'Modifier - {facture.numero}',
        'bouton': 'Enregistrer',
        'facture': facture
    })


@login_required
def supprimer_facture(request, pk):
    facture = get_object_or_404(Facture, pk=pk, utilisateur=request.user)

    if request.method == 'POST':
        numero = facture.numero
        facture.delete()
        messages.success(request, f'Facture {numero} supprimée.')
        return redirect('liste_factures')

    return render(request, 'factures/confirmer_suppression.html', {'facture': facture})


@login_required
def changer_statut_facture(request, pk):
    facture = get_object_or_404(Facture, pk=pk, utilisateur=request.user)

    if request.method == 'POST':
        nouveau_statut = request.POST.get('statut')
        if nouveau_statut in ['non_payee', 'payee', 'annulee']:
            facture.statut = nouveau_statut
            facture.save()
            messages.success(request, f'Statut mis à jour : {facture.get_statut_display()}')

    return redirect('detail_facture', pk=pk)


@login_required
def telecharger_pdf_facture(request, pk):
    facture = get_object_or_404(
        Facture.objects.select_related('client__pays_obj'),
        pk=pk, 
        utilisateur=request.user
    )
    from .pdf import generer_pdf_facture

    buffer = generer_pdf_facture(facture)

    nom_fichier = f"facture_{facture.numero}.pdf"
    chemin_relatif = f"factures/pdf/{nom_fichier}"
    chemin_complet = os.path.join(settings.MEDIA_ROOT, chemin_relatif)

    os.makedirs(os.path.dirname(chemin_complet), exist_ok=True)

    with open(chemin_complet, 'wb') as f:
        f.write(buffer.getvalue())

    facture.fichier_pdf = chemin_relatif
    facture.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    return response