from django.db import models
from django.contrib.auth.models import User


class LoginHistory(models.Model):
    """Historique des connexions utilisateurs."""
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    date       = models.DateTimeField(auto_now_add=True)
    succes     = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date']
        verbose_name = "Historique connexion"

    def __str__(self):
        return f"{self.user.username} — {self.date:%d/%m/%Y %H:%M} — {'✅' if self.succes else '❌'}"

    @property
    def navigateur(self):
        ua = self.user_agent.lower()
        if 'chrome' in ua:  return 'Chrome'
        if 'firefox' in ua: return 'Firefox'
        if 'safari' in ua:  return 'Safari'
        if 'edge' in ua:    return 'Edge'
        return 'Autre'

    @property
    def os(self):
        ua = self.user_agent.lower()
        if 'windows' in ua: return 'Windows'
        if 'android' in ua: return 'Android'
        if 'iphone' in ua:  return 'iPhone'
        if 'mac' in ua:     return 'Mac'
        if 'linux' in ua:   return 'Linux'
        return 'Autre'


class Annonce(models.Model):
    """Annonces système affichées à tous les utilisateurs."""
    TYPE_CHOICES = [
        ('info',    'Information'),
        ('warning', 'Avertissement'),
        ('success', 'Succès'),
        ('danger',  'Urgent'),
    ]
    titre      = models.CharField(max_length=200)
    message    = models.TextField()
    type_annonce = models.CharField(max_length=10, choices=TYPE_CHOICES, default='info')
    active     = models.BooleanField(default=True)
    date_debut = models.DateTimeField()
    date_fin   = models.DateTimeField(null=True, blank=True)
    creee_par  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Annonce"

    def __str__(self):
        return self.titre


class MaintenanceMode(models.Model):
    """Mode maintenance du site."""
    actif       = models.BooleanField(default=False)
    message     = models.TextField(
        default="Le site est actuellement en maintenance. Veuillez revenir plus tard."
    )
    date_debut  = models.DateTimeField(null=True, blank=True)
    date_fin    = models.DateTimeField(null=True, blank=True)
    active_par  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "Mode maintenance"

    def __str__(self):
        return f"Maintenance — {'Actif' if self.actif else 'Inactif'}"

    @classmethod
    def est_actif(cls):
        return cls.objects.filter(actif=True).exists()

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj