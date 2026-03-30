# taxes/models.py
from django.db import models
from django.core.exceptions import ValidationError


class Pays(models.Model):
    """Modèle pour un pays (sans taxe)"""
    nom = models.CharField(max_length=100, verbose_name="Pays")
    code = models.CharField(max_length=10, unique=True, verbose_name="Code ISO")
    devise = models.CharField(max_length=10, default='FCFA', verbose_name="Devise")
    devise_symbole = models.CharField(max_length=5, default='FCFA', verbose_name="Symbole devise")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    # Champs pour compatibilité avec l'ancien système
    type_taxe_defaut = models.CharField(max_length=50, blank=True, verbose_name="Type de taxe par défaut")
    taux_defaut = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Taux par défaut (%)")

    class Meta:
        ordering = ['nom']
        verbose_name = "Pays"
        verbose_name_plural = "Pays"

    def __str__(self):
        return self.nom

    def get_taxes_actives(self, province=None):
        """
        Retourne toutes les taxes actives pour ce pays
        Optionnellement filtrer par province
        """
        taxes = self.taxes.filter(actif=True)
        if province:
            taxes = taxes.filter(
                models.Q(province=province) | models.Q(province__isnull=True)
            )
        return taxes.order_by('ordre')
    
    def get_taxes_par_defaut(self, province=None):
        """
        Retourne les taxes sélectionnées par défaut pour ce pays
        Optionnellement filtrer par province
        """
        taxes = self.taxes.filter(actif=True, par_defaut=True)
        if province:
            taxes = taxes.filter(
                models.Q(province=province) | models.Q(province__isnull=True)
            )
        return taxes.order_by('ordre')
    
    def get_taxes_pour_pdf(self, montant_ht, province=None):
        """
        Retourne les détails des taxes pour le PDF
        """
        details = []
        total_taxes_cumul = 0
        
        for taxe in self.get_taxes_actives(province):
            if taxe.cumulative:
                # Taxe cumulative : calcul sur la base incluant les taxes précédentes
                base_avec_taxes = montant_ht + total_taxes_cumul
                montant = base_avec_taxes * (taxe.taux / 100)
                total_taxes_cumul += montant
            else:
                # Taxe non cumulative : calcul sur le montant HT uniquement
                montant = montant_ht * (taxe.taux / 100)
            
            details.append({
                'id': taxe.id,
                'nom': taxe.nom,
                'code': taxe.code,
                'taux': float(taxe.taux),
                'montant': montant,
                'cumulative': taxe.cumulative,
                'province': taxe.province or ''
            })
        
        return details
    
    def get_total_taxes(self, montant_ht, province=None):
        """Retourne le montant total des taxes pour un montant HT donné"""
        details = self.get_taxes_pour_pdf(montant_ht, province)
        return sum(t['montant'] for t in details)
    
    def save(self, *args, **kwargs):
        """À la sauvegarde, créer automatiquement une taxe par défaut si nécessaire"""
        super().save(*args, **kwargs)
        
        # Si le pays a un taux par défaut mais aucune taxe, créer une taxe par défaut
        if self.taux_defaut > 0 and not self.taxes.filter(actif=True).exists():
            Taxe.objects.create(
                pays=self,
                nom=self.type_taxe_defaut or 'TVA',
                code=self.type_taxe_defaut or 'TVA',
                taux=self.taux_defaut,
                actif=True,
                ordre=1,
                par_defaut=True,
                cumulative=False,
                description=f"Taxe par défaut pour {self.nom}"
            )


class Taxe(models.Model):
    """Modèle pour une taxe individuelle (TPS, TVQ, TVA, etc.)"""
    pays = models.ForeignKey(
        Pays, 
        on_delete=models.CASCADE, 
        related_name='taxes',
        verbose_name="Pays"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom de la taxe")
    code = models.CharField(max_length=10, verbose_name="Code de la taxe")
    taux = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="Taux (%)",
        help_text="Ex: 5.00 pour TPS, 9.975 pour TVQ"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    ordre = models.IntegerField(default=0, verbose_name="Ordre d'affichage")
    description = models.TextField(blank=True, verbose_name="Description")
    par_defaut = models.BooleanField(
        default=False, 
        verbose_name="Sélectionnée par défaut",
        help_text="Cochez si cette taxe doit être pré-sélectionnée"
    )
    
    # Champ pour indiquer si la taxe est cumulative ou non
    cumulative = models.BooleanField(
        default=False,
        verbose_name="Taxe cumulative",
        help_text="Cochez si cette taxe s'applique sur le montant incluant les autres taxes (ex: TVQ au Québec)"
    )
    
    # ✅ NOUVEAU : Champ pour la province (optionnel)
    province = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Province",
        help_text="Laisser vide si applicable à tout le pays (ex: TPS fédérale)"
    )

    class Meta:
        ordering = ['pays', 'province', 'ordre']
        unique_together = ['pays', 'code', 'province']  # Une taxe peut exister par province
        verbose_name = "Taxe"
        verbose_name_plural = "Taxes"

    def __str__(self):
        if self.province:
            return f"{self.code} - {self.taux}% ({self.pays.nom} - {self.province})"
        return f"{self.code} - {self.taux}% ({self.pays.nom})"

    def get_montant(self, montant_ht, taxes_cumulatives_precedentes=0):
        """
        Calcule le montant de la taxe pour un montant HT donné.
        Pour les taxes cumulatives, on ajoute les taxes précédentes à la base.
        """
        if self.cumulative:
            base = montant_ht + taxes_cumulatives_precedentes
            return base * (self.taux / 100)
        else:
            return montant_ht * (self.taux / 100)
    
    def clean(self):
        """Validation du modèle"""
        if self.taux < 0:
            raise ValidationError("Le taux de taxe ne peut pas être négatif.")
        if self.taux > 100:
            raise ValidationError("Le taux de taxe ne peut pas dépasser 100%.")


class PaysTaxe(models.Model):
    """Modèle legacy pour compatibilité - À migrer progressivement"""
    nom = models.CharField(max_length=100, verbose_name="Pays")
    code = models.CharField(max_length=10, unique=True, verbose_name="Code ISO")
    type_taxe = models.CharField(max_length=50, verbose_name="Type de taxe",
                                  help_text="Ex: TVA, GST, Sales Tax, IVA...")
    taux_defaut = models.DecimalField(max_digits=5, decimal_places=2,
                                      verbose_name="Taux par défaut (%)")
    actif = models.BooleanField(default=True)
    
    # Lien vers le nouveau modèle Pays
    pays_migre = models.ForeignKey(
        Pays,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Pays migré"
    )

    class Meta:
        ordering = ['nom']
        verbose_name = "Pays / Taxe (Legacy)"
        verbose_name_plural = "Pays / Taxes (Legacy)"

    def __str__(self):
        return f"{self.nom} ({self.type_taxe} {self.taux_defaut}%)"
    
    def migrer_vers_nouveau_modele(self):
        """Migre les données vers le nouveau modèle"""
        from django.db import transaction
        
        with transaction.atomic():
            # Créer ou récupérer le pays
            pays, created = Pays.objects.get_or_create(
                code=self.code,
                defaults={
                    'nom': self.nom,
                    'actif': self.actif,
                    'type_taxe_defaut': self.type_taxe,
                    'taux_defaut': self.taux_defaut
                }
            )
            
            # Créer la taxe
            taxe, created = Taxe.objects.get_or_create(
                pays=pays,
                code=self.type_taxe[:10],
                province=None,  # Taxe générale, sans province
                defaults={
                    'nom': self.type_taxe,
                    'taux': self.taux_defaut,
                    'actif': self.actif,
                    'ordre': 1,
                    'par_defaut': True,
                    'cumulative': False,
                    'description': f"Taxe héritée de l'ancien système: {self.type_taxe}"
                }
            )
            
            # Mettre à jour la référence
            self.pays_migre = pays
            self.save()
            
            return pays, taxe