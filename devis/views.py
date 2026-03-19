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

    nb_total    = Devis.objects.filter(utilisateur=request.user).count()
    nb_attente  = Devis.objects.filter(utilisateur=request.user, statut='en_attente').count()
    nb_acceptes = Devis.objects.filter(utilisateur=request.user, statut='accepte').count()
    nb_refuses  = Devis.objects.filter(utilisateur=request.user, statut='refuse').count()

    return render(request, 'devis/liste_devis.html', {
        'devis':       devis,
        'statut':      statut,
        'recherche':   recherche,
        'nb_total':    nb_total,
        'nb_attente':  nb_attente,
        'nb_acceptes': nb_acceptes,
        'nb_refuses':  nb_refuses,
    })


@login_required
def ajouter_devis(request):
    if request.method == 'POST':
        form    = DevisForm(request.POST, user=request.user)
        formset = LigneDevisFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            devis = form.save(commit=False)
            devis.utilisateur = request.user
            devis.numero = generer_numero_devis(request.user)
            devis.save()

            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.devis = devis
                    ligne.save()

            messages.success(request, f'✅ Devis {devis.numero} créé avec succès !')
            return redirect('detail_devis', pk=devis.pk)
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs dans le formulaire.')
            print(f"❌ ERREURS FORM: {form.errors}")
            print(f"❌ ERREURS FORMSET: {formset.errors}")
            print(f"❌ ERREURS NON-FORM: {formset.non_form_errors()}")
    else:
        form    = DevisForm(user=request.user)
        formset = LigneDevisFormSet(prefix='lignes', user=request.user)

    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

    return render(request, 'devis/form_devis.html', {
        'form':              form,
        'formset':           formset,
        'produits':          produits,
        'lignes_existantes': [],
        'titre':             'Créer un devis',
        'bouton':            'Créer le devis',
    })


@login_required
def detail_devis(request, pk):
    devis  = get_object_or_404(Devis, pk=pk, utilisateur=request.user)
    lignes = devis.lignes.all().select_related('produit')

    return render(request, 'devis/detail_devis.html', {
        'devis':  devis,
        'lignes': lignes,
    })


@login_required
def modifier_devis(request, pk):
    devis = get_object_or_404(Devis, pk=pk, utilisateur=request.user)

    if devis.transforme_en_facture:
        messages.error(request, '❌ Ce devis a déjà été transformé en facture.')
        return redirect('detail_devis', pk=pk)

    if request.method == 'POST':
        form    = DevisForm(request.POST, user=request.user, instance=devis)
        formset = LigneDevisFormSet(request.POST, prefix='lignes', user=request.user)

        if form.is_valid() and formset.is_valid():
            form.save()
            devis.lignes.all().delete()

            for ligne_form in formset:
                if ligne_form.cleaned_data and not ligne_form.cleaned_data.get('DELETE'):
                    ligne = ligne_form.save(commit=False)
                    ligne.devis = devis
                    ligne.save()

            messages.success(request, f'✏️ Devis {devis.numero} modifié avec succès !')
            return redirect('detail_devis', pk=devis.pk)
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs.')
            print(f"❌ ERREURS FORM: {form.errors}")
            print(f"❌ ERREURS FORMSET: {formset.errors}")

        # En cas d'erreur POST, repasser les lignes existantes depuis POST
        lignes_existantes = []
    else:
        form = DevisForm(user=request.user, instance=devis)
        formset = LigneDevisFormSet(prefix='lignes', user=request.user)
        # ✅ Lignes existantes passées directement au template
        lignes_existantes = list(devis.lignes.all().select_related('produit'))

    produits = Produit.objects.filter(
        user=request.user, actif=True
    ).select_related('pays', 'type_taxe').order_by('nom')

    return render(request, 'devis/form_devis.html', {
        'form':              form,
        'formset':           formset,
        'produits':          produits,
        'lignes_existantes': lignes_existantes,  # ✅ clé pour le template
        'titre':             f'Modifier - {devis.numero}',
        'bouton':            'Enregistrer',
        'devis':             devis,
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
        from django.utils import timezone
        import datetime

        client = devis.client
        pays_facture      = devis.pays or client.pays_nom or ''
        type_taxe_facture = devis.type_taxe or client.type_taxe_nom or 'TVA'
        taux_taxe_facture = devis.taux_taxe or client.taux_tva or 0

        facture = Facture.objects.create(
            utilisateur   = request.user,
            client        = client,
            devis         = devis,
            numero        = generer_numero_facture(request.user),
            date_echeance = timezone.now().date() + datetime.timedelta(days=30),
            notes         = devis.notes,
            statut        = 'non_payee',
            pays          = pays_facture,
            type_taxe     = type_taxe_facture,
            taux_taxe     = taux_taxe_facture,
        )

        for ligne in devis.lignes.all().select_related('produit'):
            LigneFacture.objects.create(
                facture       = facture,
                description   = ligne.description,
                quantite      = ligne.quantite,
                prix_unitaire = ligne.prix_unitaire,
                tva           = ligne.tva,
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

    nom_fichier    = f"devis_{devis.numero}.pdf"
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

    nb_clients          = Client.objects.filter(utilisateur=request.user).count()
    nb_devis            = Devis.objects.filter(utilisateur=request.user).count()
    nb_devis_en_attente = Devis.objects.filter(utilisateur=request.user, statut='en_attente').count()
    nb_factures         = Facture.objects.filter(utilisateur=request.user).count()
    nb_factures_payees  = Facture.objects.filter(utilisateur=request.user, statut='payee').count()

    factures_payees  = Facture.objects.filter(utilisateur=request.user, statut='payee')
    ca_total         = sum(f.calculer_total_ttc() for f in factures_payees)
    factures_attente = Facture.objects.filter(utilisateur=request.user, statut='non_payee')
    montant_attente  = sum(f.calculer_total_ttc() for f in factures_attente)

    derniers_devis     = Devis.objects.filter(utilisateur=request.user).order_by('-date_creation')[:5]
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
    devis_statuts_data   = [
        Devis.objects.filter(utilisateur=request.user, statut='en_attente').count(),
        Devis.objects.filter(utilisateur=request.user, statut='accepte').count(),
        Devis.objects.filter(utilisateur=request.user, statut='refuse').count(),
    ]
    factures_statuts_labels = ['Non payées', 'Payées', 'Annulées']
    factures_statuts_data   = [
        Facture.objects.filter(utilisateur=request.user, statut='non_payee').count(),
        Facture.objects.filter(utilisateur=request.user, statut='payee').count(),
        Facture.objects.filter(utilisateur=request.user, statut='annulee').count(),
    ]

    return render(request, 'tableau_de_bord.html', {
        'nb_clients':              nb_clients,
        'nb_devis':                nb_devis,
        'nb_devis_en_attente':     nb_devis_en_attente,
        'nb_factures':             nb_factures,
        'nb_factures_payees':      nb_factures_payees,
        'ca_total':                ca_total,
        'montant_attente':         montant_attente,
        'derniers_devis':          derniers_devis,
        'dernieres_factures':      dernieres_factures,
        'mois_labels':             json.dumps(mois_labels),
        'devis_par_mois':          json.dumps(devis_par_mois),
        'factures_par_mois':       json.dumps(factures_par_mois),
        'ca_labels':               json.dumps(ca_labels),
        'ca_par_mois':             json.dumps(ca_par_mois),
        'devis_statuts_labels':    json.dumps(devis_statuts_labels),
        'devis_statuts_data':      json.dumps(devis_statuts_data),
        'factures_statuts_labels': json.dumps(factures_statuts_labels),
        'factures_statuts_data':   json.dumps(factures_statuts_data),
    })