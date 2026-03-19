from django.db import models
from django.contrib.auth.models import User
from clients.models import Client
from devis.models import Devis


class Facture(models.Model):
    STATUT_CHOICES = [
        ('non_payee', 'Non payée'),
        ('payee',     'Payée'),
        ('annulee',   'Annulée'),
    ]

    utilisateur   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='factures')
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='factures')
    devis         = models.OneToOneField(Devis, on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='facture')
    numero        = models.CharField(max_length=20, unique=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateField()
    statut        = models.CharField(max_length=20, choices=STATUT_CHOICES, default='non_payee')
    notes         = models.TextField(blank=True)
    fichier_pdf   = models.FileField(upload_to='factures/pdf/', blank=True, null=True)

    # ── Taxe par pays ──────────────────────────────────────────
    pays      = models.CharField(max_length=100, blank=True, default='',
                                  verbose_name="Pays")
    type_taxe = models.CharField(max_length=50, blank=True, default='TVA',
                                  verbose_name="Type de taxe")
    taux_taxe = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                    verbose_name="Taux de taxe (%)")

    def __str__(self):
        return f"Facture {self.numero} - {self.client}"

    def calculer_total_ht(self):
        return sum(ligne.total_ht() for ligne in self.lignes.all())

    def calculer_tva(self):
        return sum(ligne.montant_tva() for ligne in self.lignes.all())

    def calculer_total_ttc(self):
        return self.calculer_total_ht() + self.calculer_tva()

    class Meta:
        ordering      = ['-date_creation']
        verbose_name  = 'Facture'
        verbose_name_plural = 'Factures'


class LigneFacture(models.Model):
    facture       = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')
    description   = models.CharField(max_length=255)
    quantite      = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    tva           = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)

    def total_ht(self):
        return self.quantite * self.prix_unitaire

    def montant_tva(self):
        return self.total_ht() * self.tva / 100

    def total_ttc(self):
        return self.total_ht() + self.montant_tva()

    def __str__(self):
        return f"{self.description} x{self.quantite}"

    class Meta:
        verbose_name        = 'Ligne de facture'
        verbose_name_plural = 'Lignes de facture'