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
        form    = FactureForm(request.user, request.POST)
        formset = LigneFactureFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            facture = form.save(commit=False)
            facture.utilisateur = request.user
            facture.numero = generer_numero_facture(request.user)
            facture.save()

            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.facture = facture
                    ligne.save()

            messages.success(request, f'✅ Facture {facture.numero} créée !')
            return redirect('detail_facture', pk=facture.pk)
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs.')
    else:
        form    = FactureForm(request.user)
        formset = LigneFactureFormSet(prefix='lignes', user=request.user)

    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

    return render(request, 'factures/form_facture.html', {
        'form':              form,
        'formset':           formset,
        'produits':          produits,
        'lignes_existantes': [],
        'titre':             'Créer une facture',
        'bouton':            'Créer la facture'
    })


@login_required
def detail_facture(request, pk):
    # ✅ Correction : ajout de select_related('client__pays_obj')
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
    # ✅ Correction : ajout de select_related('client__pays_obj')
    facture = get_object_or_404(
        Facture.objects.select_related('client__pays_obj'),
        pk=pk, 
        utilisateur=request.user
    )

    if facture.statut == 'payee':
        messages.error(request, '❌ Une facture payée ne peut pas être modifiée.')
        return redirect('detail_facture', pk=pk)

    if request.method == 'POST':
        form    = FactureForm(request.user, request.POST, instance=facture)
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
        # ✅ Lignes existantes passées au template
        lignes_existantes = list(facture.lignes.all())

    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

    return render(request, 'factures/form_facture.html', {
        'form':              form,
        'formset':           formset,
        'produits':          produits,
        'lignes_existantes': lignes_existantes,
        'titre':             f'Modifier - {facture.numero}',
        'bouton':            'Enregistrer',
        'facture':           facture
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
    # ✅ Correction : ajout de select_related('client__pays_obj')
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