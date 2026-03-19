from django.db import models

class PaysTaxe(models.Model):
    nom = models.CharField(max_length=100, verbose_name="Pays")
    code = models.CharField(max_length=10, unique=True, verbose_name="Code ISO")
    type_taxe = models.CharField(max_length=50, verbose_name="Type de taxe",
                                  help_text="Ex: TVA, GST, Sales Tax, IVA...")
    taux_defaut = models.DecimalField(max_digits=5, decimal_places=2,
                                      verbose_name="Taux par défaut (%)")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['nom']
        verbose_name = "Pays / Taxe"
        verbose_name_plural = "Pays / Taxes"

    def __str__(self):
        return f"{self.nom} ({self.type_taxe} {self.taux_defaut}%)"