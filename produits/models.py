# produits/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from decimal import Decimal

class Categorie(models.Model):
    """Catégories de produits (par utilisateur)"""
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['nom']
        unique_together = ['nom', 'user']
    
    def __str__(self):
        return self.nom
    
    def nombre_produits(self):
        """Retourne le nombre de produits dans cette catégorie"""
        return self.produits.count()


class Pays(models.Model):
    """Table des pays avec leurs configurations de base"""
    code = models.CharField(max_length=2, unique=True, verbose_name="Code pays (ISO)")
    nom = models.CharField(max_length=100, verbose_name="Nom du pays")
    devise = models.CharField(max_length=3, default='FCFA', verbose_name="Code devise (ISO)")
    symbole_devise = models.CharField(max_length=5, default='FCFA', verbose_name="Symbole devise")
    
    class Meta:
        verbose_name = "Pays"
        verbose_name_plural = "Pays"
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.nom} ({self.devise} - {self.symbole_devise})"


class TypeTaxe(models.Model):
    """Types de taxes disponibles par pays (TVA, GST, Sales Tax, etc.)"""
    pays = models.ForeignKey(Pays, on_delete=models.CASCADE, related_name='types_taxe')
    nom = models.CharField(max_length=50, verbose_name="Nom de la taxe")
    code = models.CharField(max_length=20, verbose_name="Code (TVA, GST, etc.)")
    description = models.TextField(blank=True, verbose_name="Description")
    est_taxe_composee = models.BooleanField(default=False, verbose_name="Est une taxe composée?")
    
    class Meta:
        verbose_name = "Type de taxe"
        verbose_name_plural = "Types de taxes"
        ordering = ['pays', 'nom']
        unique_together = ['pays', 'code']
    
    def __str__(self):
        return f"{self.pays.nom} - {self.nom} ({self.code})"
    
    def taux_par_defaut(self):
        """Retourne le taux par défaut pour ce type de taxe"""
        taux_defaut = self.taux.filter(est_defaut=True).first()
        if taux_defaut:
            return taux_defaut.taux
        return Decimal('0')


class TauxTaxe(models.Model):
    """Taux spécifiques pour chaque type de taxe (par région/province)"""
    type_taxe = models.ForeignKey(TypeTaxe, on_delete=models.CASCADE, related_name='taux')
    region = models.CharField(max_length=100, blank=True, verbose_name="Région/Province")
    code_region = models.CharField(max_length=10, blank=True, verbose_name="Code région")
    taux = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Taux (%)")
    est_defaut = models.BooleanField(default=False, verbose_name="Taux par défaut")
    
    class Meta:
        verbose_name = "Taux de taxe"
        verbose_name_plural = "Taux de taxes"
        ordering = ['type_taxe__pays', 'region']
        unique_together = ['type_taxe', 'region']
    
    def __str__(self):
        if self.region:
            return f"{self.type_taxe} - {self.region}: {self.taux}%"
        return f"{self.type_taxe}: {self.taux}%"
    
    def save(self, *args, **kwargs):
        # S'assurer qu'un seul taux par défaut par type de taxe
        if self.est_defaut:
            TauxTaxe.objects.filter(type_taxe=self.type_taxe, est_defaut=True).update(est_defaut=False)
        super().save(*args, **kwargs)


class Province(models.Model):
    """Pour les pays avec provinces/états (Canada, USA, etc.)"""
    pays = models.ForeignKey(Pays, on_delete=models.CASCADE, related_name='provinces')
    code = models.CharField(max_length=3, verbose_name="Code province")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    
    # Configuration fiscale
    tps = models.DecimalField(max_digits=5, decimal_places=2, default=5.0, verbose_name="TPS (%)")
    tvq = models.DecimalField(max_digits=5, decimal_places=2, default=9.975, verbose_name="TVQ (%)")
    tvh = models.BooleanField(default=False, verbose_name="TVH (Taxe harmonisée)")
    
    class Meta:
        verbose_name = "Province"
        verbose_name_plural = "Provinces"
        unique_together = ['pays', 'code']
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.nom} ({self.code}) - {self.pays.nom}"
    
    def taux_taxe_total(self):
        """Calculer le taux de taxe total selon la province"""
        if self.tvh:
            return Decimal('15.0')
        return Decimal(str(self.tps)) + Decimal(str(self.tvq))
    
    def description_taxe(self):
        """Description des taxes applicables"""
        if self.tvh:
            return "TVH 15% (Taxe harmonisée)"
        return f"TPS {self.tps}% + TVQ {self.tvq}%"


class Produit(models.Model):
    """Modèle principal pour les produits/services"""
    
    UNITE_CHOICES = [
        ('piece', 'Pièce'),
        ('heure', 'Heure'),
        ('jour', 'Jour'),
        ('mois', 'Mois'),
        ('m2', 'Mètre carré'),
        ('m3', 'Mètre cube'),
        ('kg', 'Kilogramme'),
        ('litre', 'Litre'),
        ('forfait', 'Forfait'),
        ('service', 'Service'),
    ]
    
    # Informations de base
    reference = models.CharField(max_length=50, verbose_name="Référence")
    nom = models.CharField(max_length=200, verbose_name="Nom du produit")
    slug = models.SlugField(max_length=200, blank=True)
    description = models.TextField(blank=True, verbose_name="Description")
    categorie = models.ForeignKey(
        Categorie, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='produits',
        verbose_name="Catégorie"
    )
    
    # Prix et taxes
    prix_ht = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        verbose_name="Prix HT"
    )
    pays = models.ForeignKey(
        Pays, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="Pays de vente"
    )
    type_taxe = models.ForeignKey(
        TypeTaxe, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Type de taxe"
    )
    taux_taxe_personnalise = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        verbose_name="Taux personnalisé (%)",
        help_text="Laissez à 0 pour utiliser le taux par défaut"
    )
    
    # Pour la rétrocompatibilité (à supprimer plus tard)
    province = models.ForeignKey(
        Province, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Province (Canada)"
    )
    
    # Unité
    unite = models.CharField(
        max_length=20, 
        choices=UNITE_CHOICES, 
        default='piece',
        verbose_name="Unité de vente"
    )
    
    # Stock (optionnel)
    stock = models.IntegerField(
        null=True, 
        blank=True, 
        validators=[MinValueValidator(0)],
        verbose_name="Stock initial"
    )
    stock_alerte = models.IntegerField(
        null=True, 
        blank=True, 
        validators=[MinValueValidator(0)],
        verbose_name="Seuil d'alerte"
    )
    
    # Métadonnées
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='produits',
        verbose_name="Utilisateur"
    )
    actif = models.BooleanField(default=True, verbose_name="Produit actif")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")
    
    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ['-date_creation']
        unique_together = ['reference', 'user']
    
    def __str__(self):
        return f"{self.reference} - {self.nom}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.reference}-{self.nom}")[:200]
        super().save(*args, **kwargs)
    
    @property
    def taux_tva(self):
        """Obtenir le taux de TVA effectif"""
        # Priorité 1: Taux personnalisé
        if self.taux_taxe_personnalise and self.taux_taxe_personnalise > 0:
            return self.taux_taxe_personnalise
        
        # Priorité 2: Type de taxe avec taux par défaut
        if self.type_taxe:
            taux_defaut = self.type_taxe.taux_par_defaut()
            if taux_defaut > 0:
                return taux_defaut
        
        # Priorité 3: Province (rétrocompatibilité)
        if self.province:
            return self.province.taux_taxe_total()
        
        return Decimal('0')
    
    @property
    def prix_ttc(self):
        """Calculer le prix TTC"""
        try:
            taux = self.taux_tva
            if not isinstance(taux, Decimal):
                taux = Decimal(str(taux))
            return self.prix_ht * (Decimal('1') + taux / Decimal('100'))
        except (TypeError, ValueError, AttributeError):
            return self.prix_ht
    
    @property
    def devise_symbole(self):
        """Obtenir le symbole de la devise"""
        if self.pays and hasattr(self.pays, 'symbole_devise'):
            return self.pays.symbole_devise
        return 'FCFA'
    
    @property
    def description_taxe(self):
        """Description textuelle des taxes applicables"""
        if self.taux_taxe_personnalise and self.taux_taxe_personnalise > 0:
            return f"Taux personnalisé: {self.taux_taxe_personnalise}%"
        if self.type_taxe:
            taux_defaut = self.type_taxe.taux_par_defaut()
            if taux_defaut > 0:
                return f"{self.type_taxe.nom}: {taux_defaut}%"
        if self.province:
            return self.province.description_taxe()
        return "Aucune taxe"
    
    def stock_bas(self):
        """Vérifier si le stock est bas"""
        if self.stock is not None and self.stock_alerte:
            return self.stock <= self.stock_alerte
        return False
    
    def valeur_stock(self):
        """Valeur totale du stock"""
        if self.stock:
            return self.prix_ht * Decimal(str(self.stock))
        return Decimal('0')


# Signals pour maintenir la cohérence
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

@receiver(pre_save, sender=Produit)
def produit_pre_save(sender, instance, **kwargs):
    """Nettoie les données avant sauvegarde"""
    if instance.stock == '':
        instance.stock = None
    if instance.stock_alerte == '':
        instance.stock_alerte = None