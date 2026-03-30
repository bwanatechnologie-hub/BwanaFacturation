# clients/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Client
from .forms import ClientForm
# ✅ Importer depuis taxes.models
from taxes.models import Pays, Taxe  # ← Changement clé !


def get_pays_context():
    """Retourne la liste des pays actifs"""
    return Pays.objects.filter(actif=True).order_by('nom')


@login_required
def liste_clients(request):
    recherche = request.GET.get('q', '')
    clients = Client.objects.filter(utilisateur=request.user).select_related('pays_obj')

    if recherche:
        clients = clients.filter(nom__icontains=recherche) | \
                  clients.filter(entreprise__icontains=recherche) | \
                  clients.filter(email__icontains=recherche)

    return render(request, 'clients/liste_clients.html', {
        'clients':    clients,
        'recherche':  recherche,
        'nb_clients': clients.count()
    })


@login_required
def ajouter_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            client = form.save(commit=False)
            client.utilisateur = request.user
            client.save()
            messages.success(request, f'✅ Client "{client.nom}" ajouté avec succès !')
            return redirect('liste_clients')
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs.')
    else:
        form = ClientForm()

    return render(request, 'clients/form_client.html', {
        'form':      form,
        'titre':     'Ajouter un client',
        'bouton':    'Ajouter',
        'pays_list': get_pays_context(),
    })


@login_required
def modifier_client(request, pk):
    client = get_object_or_404(Client, pk=pk, utilisateur=request.user)

    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f'✏️ Client "{client.nom}" modifié avec succès !')
            return redirect('liste_clients')
        else:
            messages.error(request, '❌ Veuillez corriger les erreurs.')
    else:
        form = ClientForm(instance=client)

    return render(request, 'clients/form_client.html', {
        'form':      form,
        'titre':     f'Modifier - {client.nom}',
        'bouton':    'Modifier',
        'client':    client,
        'pays_list': get_pays_context(),
    })


@login_required
def supprimer_client(request, pk):
    client = get_object_or_404(Client, pk=pk, utilisateur=request.user)

    if request.method == 'POST':
        nom = client.nom
        client.delete()
        messages.success(request, f'🗑️ Client "{nom}" supprimé.')
        return redirect('liste_clients')

    return render(request, 'clients/confirmer_suppression.html', {'client': client})


@login_required
def detail_client(request, pk):
    client = get_object_or_404(
        Client.objects.select_related('pays_obj'),
        pk=pk, utilisateur=request.user
    )
    return render(request, 'clients/detail_client.html', {
        'client':   client,
        'devis':    client.devis.all(),
        'factures': client.factures.all(),
    })


# ══════════════════════════════════════════════════
# API JSON — infos client pour le formulaire devis
# ══════════════════════════════════════════════════
@login_required
def api_client_info(request, pk):
    """Retourne devise + taxes du client pour le JS du formulaire devis"""
    client = get_object_or_404(Client, pk=pk, utilisateur=request.user)

    # ✅ Récupérer les taxes multiples du pays du client
    taxes = []
    if client.pays_obj:
        for taxe in client.pays_obj.taxes.filter(actif=True).order_by('ordre'):
            taxes.append({
                'id': taxe.id,
                'nom': taxe.nom,
                'code': taxe.code,
                'taux_defaut': float(taxe.taux),
                'cumulative': taxe.cumulative,
                'par_defaut': taxe.par_defaut,
                'ordre': taxe.ordre
            })

    return JsonResponse({
        'id': client.pk,
        'nom': str(client),
        'pays_code': client.pays_obj.code if client.pays_obj else '',
        'pays_nom': client.pays_obj.nom if client.pays_obj else '',
        'devise': client.devise,
        'taux_tva': float(client.taux_tva),
        'type_taxe': client.type_taxe_nom,
        'taxes': taxes,
        'province': client.province or '',
    })


# ══════════════════════════════════════════════════
# API : Récupérer les taxes du client
# ══════════════════════════════════════════════════
@login_required
def api_client_taxes(request, pk):
    """
    API pour récupérer les taxes disponibles pour un client
    Utilisée par le formulaire devis pour afficher les checkboxes
    """
    try:
        client = get_object_or_404(Client, pk=pk, utilisateur=request.user)
        
        taxes = []
        if client.pays_obj:
            for taxe in client.pays_obj.taxes.filter(actif=True).order_by('ordre'):
                taxes.append({
                    'id': taxe.id,
                    'nom': taxe.nom,
                    'code': taxe.code,
                    'taux': float(taxe.taux),
                    'cumulative': taxe.cumulative,
                    'par_defaut': taxe.par_defaut,
                    'ordre': taxe.ordre,
                    'description': taxe.description if hasattr(taxe, 'description') else ''
                })
        
        return JsonResponse({
            'success': True,
            'taxes': taxes,
            'pays': client.pays_obj.nom if client.pays_obj else '',
            'pays_code': client.pays_obj.code if client.pays_obj else '',
            'devise': client.devise,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=400)