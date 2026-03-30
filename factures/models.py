# factures/models.py
from django.db import models
from django.contrib.auth.models import User
from clients.models import Client
from devis.models import Devis
import secrets


class Facture(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente d\'approbation'),
        ('approuvee', 'Approuvée'),
        ('rejetee', 'Rejetée'),
        ('non_payee', 'Non payée'),
        ('payee', 'Payée'),
        ('annulee', 'Annulée'),
    ]

    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='factures')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='factures')
    devis = models.OneToOneField(Devis, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='facture')
    numero = models.CharField(max_length=20, unique=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    notes = models.TextField(blank=True)
    fichier_pdf = models.FileField(upload_to='factures/pdf/', blank=True, null=True)

    # ── Taxe par pays (ancien système - gardé pour compatibilité) ──
    pays = models.CharField(max_length=100, blank=True, default='',
                            verbose_name="Pays")
    type_taxe = models.CharField(max_length=50, blank=True, default='TVA',
                                  verbose_name="Type de taxe")
    taux_taxe = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                    verbose_name="Taux de taxe (%)")
    
    # ✅ NOUVEAU : Relation ManyToMany pour plusieurs taxes
    taxes = models.ManyToManyField(
        'taxes.Taxe',
        blank=True,
        related_name='factures',
        verbose_name="Taxes applicables"
    )
    
    # ── Champs d'approbation ──
    approuve_par = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='factures_approuvees',
        verbose_name="Approuvé par"
    )
    approuve_le = models.DateTimeField(null=True, blank=True, verbose_name="Date d'approbation")
    commentaire_approbation = models.TextField(blank=True, verbose_name="Commentaire d'approbation")
    
    accepte_par_client = models.BooleanField(null=True, blank=True, verbose_name="Accepté par le client")
    accepte_client_le = models.DateTimeField(null=True, blank=True, verbose_name="Date d'acceptation client")
    
    # Tokens pour liens publics
    token_approbation = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name="Token approbation"
    )
    token_client = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name="Token client"
    )

    def generer_tokens(self):
        """Génère des tokens uniques pour les liens d'approbation et client"""
        self.token_approbation = secrets.token_urlsafe(32)
        self.token_client = secrets.token_urlsafe(32)

    def __str__(self):
        return f"Facture {self.numero} - {self.client}"

    def calculer_total_ht(self):
        return sum(ligne.total_ht() for ligne in self.lignes.all())

    def calculer_tva(self):
        """
        Calcule le montant total des taxes
        Gère les taxes cumulatives (ex: TVQ calculée sur HT + TPS)
        """
        total_ht = self.calculer_total_ht()
        
        # Si des taxes sont sélectionnées, utiliser la relation ManyToMany
        if self.taxes.exists():
            # Récupérer toutes les taxes actives triées par ordre
            taxes_triees = self.taxes.filter(actif=True).order_by('ordre')
            
            total_tva = 0
            base_calcul = total_ht
            total_taxes_cumul = 0
            
            for taxe in taxes_triees:
                if taxe.cumulative:
                    # Taxe cumulative : calcul sur la base incluant les taxes précédentes
                    base_avec_taxes = total_ht + total_taxes_cumul
                    montant_taxe = base_avec_taxes * (taxe.taux / 100)
                    total_taxes_cumul += montant_taxe
                else:
                    # Taxe non cumulative : calcul sur le montant HT uniquement
                    montant_taxe = total_ht * (taxe.taux / 100)
                
                total_tva += montant_taxe
            
            return total_tva
        
        # Fallback pour compatibilité avec l'ancien système
        return sum(ligne.montant_tva() for ligne in self.lignes.all())

    def calculer_total_ttc(self):
        return self.calculer_total_ht() + self.calculer_tva()
    
    def get_taxes_details(self):
        """
        Retourne les détails des taxes pour le PDF
        Gère correctement les taxes cumulatives
        """
        total_ht = self.calculer_total_ht()
        details = []
        
        if self.taxes.exists():
            # Récupérer toutes les taxes actives triées par ordre
            taxes_triees = self.taxes.filter(actif=True).order_by('ordre')
            
            total_taxes_cumul = 0
            
            for taxe in taxes_triees:
                if taxe.cumulative:
                    # Taxe cumulative : calcul sur la base incluant les taxes précédentes
                    base_avec_taxes = total_ht + total_taxes_cumul
                    montant = base_avec_taxes * (taxe.taux / 100)
                    total_taxes_cumul += montant
                else:
                    # Taxe non cumulative : calcul sur le montant HT uniquement
                    montant = total_ht * (taxe.taux / 100)
                
                details.append({
                    'id': taxe.id,
                    'nom': taxe.nom,
                    'code': taxe.code,
                    'taux': float(taxe.taux),
                    'montant': montant,
                    'cumulative': taxe.cumulative
                })
        else:
            # Fallback pour compatibilité
            details.append({
                'id': None,
                'nom': self.type_taxe or 'TVA',
                'code': self.type_taxe or 'TVA',
                'taux': float(self.taux_taxe),
                'montant': sum(ligne.montant_tva() for ligne in self.lignes.all()),
                'cumulative': False
            })
        
        return details
    
    def get_taxes_total(self):
        """Retourne le montant total des taxes"""
        return sum(t['montant'] for t in self.get_taxes_details())
    
    def get_taxes_formatted(self):
        """
        Retourne les taxes formatées pour l'affichage
        Utile pour les templates
        """
        details = self.get_taxes_details()
        formatted = []
        
        for taxe in details:
            formatted.append({
                'nom': f"{taxe['code']} ({taxe['taux']}%)",
                'montant': taxe['montant']
            })
        
        return formatted
    
    def get_devise(self):
        """Retourne la devise de la facture (depuis le client)"""
        if self.client and self.client.pays_obj:
            return self.client.pays_obj.devise_symbole
        return 'FCFA'
    
    @property
    def est_approuvee(self):
        """Vérifie si la facture a été approuvée par le supérieur"""
        return self.statut == 'approuvee'
    
    @property
    def est_rejetee(self):
        """Vérifie si la facture a été rejetée par le supérieur"""
        return self.statut == 'rejetee'
    
    @property
    def est_payee(self):
        """Vérifie si la facture a été payée"""
        return self.statut == 'payee'
    
    @property
    def est_acceptee_client(self):
        """Vérifie si le client a accepté la facture"""
        return self.accepte_par_client == True

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'


class LigneFacture(models.Model):
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')
    description = models.CharField(max_length=255)
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)

    def total_ht(self):
        return self.quantite * self.prix_unitaire

    def montant_tva(self):
        return self.total_ht() * self.tva / 100

    def total_ttc(self):
        return self.total_ht() + self.montant_tva()

    def __str__(self):
        return f"{self.description} x{self.quantite}"

    class Meta:
        verbose_name = 'Ligne de facture'
        verbose_name_plural = 'Lignes de facture'