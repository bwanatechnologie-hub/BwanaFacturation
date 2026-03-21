from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils.text import slugify
from decimal import Decimal


# ══════════════════════════════════════════════════
# UNITÉ DE VENTE — liste de base + personnalisée
# ══════════════════════════════════════════════════
class UniteVente(models.Model):
    """Unités de vente : liste de base globale + unités personnalisées par user."""

    UNITES_BASE = [
        # Quantité
        ('piece',     'Pièce'),
        ('unite',     'Unité'),
        ('lot',       'Lot'),
        ('paire',     'Paire'),
        ('douzaine',  'Douzaine'),
        ('carton',    'Carton'),
        ('boite',     'Boîte'),
        ('sac',       'Sac'),
        ('sachet',    'Sachet'),
        ('palette',   'Palette'),
        ('colis',     'Colis'),
        ('pack',      'Pack'),
        # Poids
        ('kg',        'Kilogramme'),
        ('g',         'Gramme'),
        ('tonne',     'Tonne'),
        # Volume
        ('litre',     'Litre'),
        ('ml',        'Millilitre'),
        ('m3',        'Mètre cube'),
        # Surface / Longueur
        ('m2',        'Mètre carré'),
        ('ml_lin',    'Mètre linéaire'),
        # Temps / Service
        ('heure',     'Heure'),
        ('jour',      'Jour'),
        ('semaine',   'Semaine'),
        ('mois',      'Mois'),
        ('annee',     'Année'),
        ('forfait',   'Forfait'),
        ('service',   'Service'),
        ('prestation','Prestation'),
        ('licence',   'Licence'),
        ('abonnement','Abonnement'),
    ]

    code        = models.CharField(max_length=50, verbose_name="Code")
    nom         = models.CharField(max_length=100, verbose_name="Nom affiché")
    # ── user = NULL → unité de base globale
    # ── user = FK  → unité personnalisée par cet utilisateur
    user        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='unites_vente',
        verbose_name="Utilisateur (vide = global)"
    )
    est_defaut  = models.BooleanField(default=False, verbose_name="Unité par défaut")
    ordre       = models.PositiveSmallIntegerField(default=99, verbose_name="Ordre d'affichage")

    class Meta:
        verbose_name        = "Unité de vente"
        verbose_name_plural = "Unités de vente"
        ordering            = ['ordre', 'nom']

    def __str__(self):
        return self.nom

    @classmethod
    def pour_user(cls, user):
        """Retourne toutes les unités disponibles pour un utilisateur
        (globales + ses unités personnalisées)."""
        from django.db.models import Q
        return cls.objects.filter(Q(user__isnull=True) | Q(user=user)).order_by('ordre', 'nom')


class Categorie(models.Model):
    """Catégories de produits (par utilisateur)"""
    nom           = models.CharField(max_length=100)
    description   = models.TextField(blank=True)
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering            = ['nom']
        unique_together     = ['nom', 'user']

    def __str__(self):
        return self.nom

    def nombre_produits(self):
        return self.produits.count()


class Pays(models.Model):
    code           = models.CharField(max_length=2,  unique=True)
    nom            = models.CharField(max_length=100)
    devise         = models.CharField(max_length=3,  default='FCFA')
    symbole_devise = models.CharField(max_length=5,  default='FCFA')

    class Meta:
        verbose_name        = "Pays"
        verbose_name_plural = "Pays"
        ordering            = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.devise} - {self.symbole_devise})"


class TypeTaxe(models.Model):
    pays              = models.ForeignKey(Pays, on_delete=models.CASCADE, related_name='types_taxe')
    nom               = models.CharField(max_length=50)
    code              = models.CharField(max_length=20)
    description       = models.TextField(blank=True)
    est_taxe_composee = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "Type de taxe"
        verbose_name_plural = "Types de taxes"
        ordering            = ['pays', 'nom']
        unique_together     = ['pays', 'code']

    def __str__(self):
        return f"{self.pays.nom} - {self.nom} ({self.code})"

    def taux_par_defaut(self):
        taux_defaut = self.taux.filter(est_defaut=True).first()
        return taux_defaut.taux if taux_defaut else Decimal('0')


class TauxTaxe(models.Model):
    type_taxe   = models.ForeignKey(TypeTaxe, on_delete=models.CASCADE, related_name='taux')
    region      = models.CharField(max_length=100, blank=True)
    code_region = models.CharField(max_length=10,  blank=True)
    taux        = models.DecimalField(max_digits=5, decimal_places=2)
    est_defaut  = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "Taux de taxe"
        verbose_name_plural = "Taux de taxes"
        ordering            = ['type_taxe__pays', 'region']
        unique_together     = ['type_taxe', 'region']

    def __str__(self):
        if self.region:
            return f"{self.type_taxe} - {self.region}: {self.taux}%"
        return f"{self.type_taxe}: {self.taux}%"

    def save(self, *args, **kwargs):
        if self.est_defaut:
            TauxTaxe.objects.filter(type_taxe=self.type_taxe, est_defaut=True).update(est_defaut=False)
        super().save(*args, **kwargs)


class Province(models.Model):
    pays = models.ForeignKey(Pays, on_delete=models.CASCADE, related_name='provinces')
    code = models.CharField(max_length=3)
    nom  = models.CharField(max_length=100)
    tps  = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    tvq  = models.DecimalField(max_digits=5, decimal_places=2, default=9.975)
    tvh  = models.BooleanField(default=False)

    class Meta:
        unique_together = ['pays', 'code']
        ordering        = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.code}) - {self.pays.nom}"

    def taux_taxe_total(self):
        if self.tvh:
            return Decimal('15.0')
        return Decimal(str(self.tps)) + Decimal(str(self.tvq))

    def description_taxe(self):
        if self.tvh:
            return "TVH 15%"
        return f"TPS {self.tps}% + TVQ {self.tvq}%"


class Produit(models.Model):
    """Modèle principal pour les produits/services"""

    # ── Informations de base
    reference   = models.CharField(max_length=50)
    nom         = models.CharField(max_length=200)
    slug        = models.SlugField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    categorie   = models.ForeignKey(
        Categorie, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='produits'
    )

    # ── Prix et taxes
    prix_ht = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    pays = models.ForeignKey(
        Pays, on_delete=models.SET_NULL,
        null=True, verbose_name="Pays de vente"
    )
    type_taxe = models.ForeignKey(
        TypeTaxe, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    taux_taxe_personnalise = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    province = models.ForeignKey(
        Province, on_delete=models.SET_NULL,
        null=True, blank=True
    )

    # ✅ Unité — FK vers UniteVente au lieu de CharField choices
    unite_vente = models.ForeignKey(
        UniteVente, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='produits',
        verbose_name="Unité de vente"
    )
    # ── Garde le champ unite pour rétrocompatibilité migrations
    unite = models.CharField(max_length=50, blank=True, default='piece')

    # ── Stock
    stock        = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    stock_alerte = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])

    # ── Métadonnées
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='produits')
    actif            = models.BooleanField(default=True)
    date_creation    = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Produit"
        verbose_name_plural = "Produits"
        ordering            = ['-date_creation']
        unique_together     = ['reference', 'user']

    def __str__(self):
        return f"{self.reference} - {self.nom}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.reference}-{self.nom}")[:200]
        super().save(*args, **kwargs)

    @property
    def unite_label(self):
        """Retourne le nom de l'unité."""
        if self.unite_vente:
            return self.unite_vente.nom
        return self.unite or 'Pièce'

    @property
    def taux_tva(self):
        if self.taux_taxe_personnalise and self.taux_taxe_personnalise > 0:
            return self.taux_taxe_personnalise
        if self.type_taxe:
            taux = self.type_taxe.taux_par_defaut()
            if taux > 0:
                return taux
        if self.province:
            return self.province.taux_taxe_total()
        return Decimal('0')

    @property
    def prix_ttc(self):
        try:
            taux = self.taux_tva
            if not isinstance(taux, Decimal):
                taux = Decimal(str(taux))
            return self.prix_ht * (Decimal('1') + taux / Decimal('100'))
        except (TypeError, ValueError, AttributeError):
            return self.prix_ht

    @property
    def devise_symbole(self):
        if self.pays and hasattr(self.pays, 'symbole_devise'):
            return self.pays.symbole_devise
        return 'FCFA'

    @property
    def description_taxe(self):
        if self.taux_taxe_personnalise and self.taux_taxe_personnalise > 0:
            return f"Taux personnalisé: {self.taux_taxe_personnalise}%"
        if self.type_taxe:
            taux = self.type_taxe.taux_par_defaut()
            if taux > 0:
                return f"{self.type_taxe.nom}: {taux}%"
        if self.province:
            return self.province.description_taxe()
        return "Aucune taxe"

    def stock_bas(self):
        if self.stock is not None and self.stock_alerte:
            return self.stock <= self.stock_alerte
        return False

    def valeur_stock(self):
        if self.stock:
            return self.prix_ht * Decimal(str(self.stock))
        return Decimal('0')


# ── Signals
from django.db.models.signals import pre_save
from django.dispatch import receiver

@receiver(pre_save, sender=Produit)
def produit_pre_save(sender, instance, **kwargs):
    if instance.stock == '':
        instance.stock = None
    if instance.stock_alerte == '':
        instance.stock_alerte = None