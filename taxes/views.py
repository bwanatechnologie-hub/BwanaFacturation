from django.http import JsonResponse
from .models import PaysTaxe

def get_taxe_pays(request):
    """API appelée en JS pour récupérer le taux d'un pays."""
    code = request.GET.get('code', '')
    try:
        pays = PaysTaxe.objects.get(code=code, actif=True)
        return JsonResponse({
            'success': True,
            'type_taxe': pays.type_taxe,
            'taux': float(pays.taux_defaut),
            'nom': pays.nom,
        })
    except PaysTaxe.DoesNotExist:
        return JsonResponse({'success': False, 'taux': 0, 'type_taxe': 'TVA'})


def liste_pays_json(request):
    """Retourne tous les pays actifs en JSON."""
    pays = PaysTaxe.objects.filter(actif=True).values(
        'code', 'nom', 'type_taxe', 'taux_defaut'
    )
    return JsonResponse({'pays': list(pays)})