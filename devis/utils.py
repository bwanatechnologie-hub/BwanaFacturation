from django.utils import timezone


def generer_numero_devis(user):
    from .models import Devis
    annee = timezone.now().year
    mois = timezone.now().month
    
    # Compter les devis de l'utilisateur ce mois
    count = Devis.objects.filter(
        utilisateur=user,
        date_creation__year=annee,
        date_creation__month=mois
    ).count()
    
    numero = f"DEV-{annee}{mois:02d}-{(count + 1):04d}"
    
    # S'assurer que le numéro est unique
    while Devis.objects.filter(numero=numero).exists():
        count += 1
        numero = f"DEV-{annee}{mois:02d}-{(count + 1):04d}"
    
    return numero


def generer_numero_facture(user):
    from factures.models import Facture
    annee = timezone.now().year
    mois = timezone.now().month
    
    count = Facture.objects.filter(
        utilisateur=user,
        date_creation__year=annee,
        date_creation__month=mois
    ).count()
    
    numero = f"FAC-{annee}{mois:02d}-{(count + 1):04d}"
    
    while Facture.objects.filter(numero=numero).exists():
        count += 1
        numero = f"FAC-{annee}{mois:02d}-{(count + 1):04d}"
    
    return numero