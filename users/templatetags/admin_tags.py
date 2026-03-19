from django import template
from django.utils import timezone

register = template.Library()


@register.simple_tag
def get_annonces():
    """Retourne les annonces actives à afficher."""
    try:
        from users.admin_models import Annonce
        now = timezone.now()
        return Annonce.objects.filter(
            active=True,
            date_debut__lte=now,
        ).filter(
            date_fin__isnull=True
        ) | Annonce.objects.filter(
            active=True,
            date_debut__lte=now,
            date_fin__gte=now,
        )
    except Exception:
        return []


@register.simple_tag
def get_maintenance():
    """Retourne l'état du mode maintenance."""
    try:
        from users.admin_models import MaintenanceMode
        return MaintenanceMode.get_instance()
    except Exception:
        return None