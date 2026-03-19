from django import forms
from .models import Produit, Categorie, Pays, Province, TypeTaxe


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = [
            'reference', 'nom', 'description', 'categorie',
            'prix_ht', 'pays', 'type_taxe', 'taux_taxe_personnalise',
            'province', 'unite', 'stock', 'stock_alerte', 'actif'
        ]
        widgets = {
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'REF-001'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du produit/service'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description détaillée...'
            }),
            'categorie': forms.Select(attrs={
                'class': 'form-select'
            }),
            'prix_ht': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'pays': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_pays'
            }),
            # ✅ type_taxe caché — rempli automatiquement par JS
            'type_taxe': forms.Select(attrs={
                'class': 'form-select d-none',
                'id': 'id_type_taxe'
            }),
            # ✅ taux_taxe_personnalise — rempli auto par JS, modifiable
            'taux_taxe_personnalise': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'province': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_province'
            }),
            'unite': forms.Select(attrs={
                'class': 'form-select'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Laissez vide si non applicable'
            }),
            'stock_alerte': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Notification quand stock bas'
            }),
            'actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les catégories par utilisateur
        if self.user:
            self.fields['categorie'].queryset = Categorie.objects.filter(user=self.user)

        # Champs optionnels
        self.fields['stock'].required              = False
        self.fields['stock_alerte'].required       = False
        self.fields['description'].required        = False
        self.fields['province'].required           = False
        self.fields['type_taxe'].required          = False
        self.fields['taux_taxe_personnalise'].required = False

        # Initialiser les provinces selon le pays
        self.fields['province'].queryset = Province.objects.none()
        if 'pays' in self.data:
            try:
                pays_id = int(self.data.get('pays'))
                self.fields['province'].queryset = Province.objects.filter(
                    pays_id=pays_id
                ).order_by('nom')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.pays:
            self.fields['province'].queryset = Province.objects.filter(
                pays=self.instance.pays
            ).order_by('nom')

        # Initialiser les types de taxe selon le pays
        self.fields['type_taxe'].queryset = TypeTaxe.objects.none()
        if 'pays' in self.data:
            try:
                pays_id = int(self.data.get('pays'))
                self.fields['type_taxe'].queryset = TypeTaxe.objects.filter(
                    pays_id=pays_id
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.pays:
            self.fields['type_taxe'].queryset = TypeTaxe.objects.filter(
                pays=self.instance.pays
            )

        # Messages d'aide
        self.fields['stock'].help_text             = "Laissez vide si vous ne gérez pas le stock"
        self.fields['stock_alerte'].help_text      = "Notification quand le stock est bas"
        self.fields['pays'].help_text              = "Détermine la devise et la TVA"
        self.fields['taux_taxe_personnalise'].help_text = "Rempli automatiquement selon le pays"

        self.fields['reference'].widget.attrs.update({'autofocus': 'autofocus'})

    def clean_reference(self):
        reference = self.cleaned_data['reference']
        if self.user:
            qs = Produit.objects.filter(user=self.user, reference=reference)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Cette référence existe déjà pour vos produits")
        return reference

    def clean(self):
        cleaned_data = super().clean()
        pays     = cleaned_data.get('pays')
        province = cleaned_data.get('province')

        if pays and pays.code == 'CA' and not province:
            self.add_error('province', "La province est requise pour le Canada")

        if province and pays and province.pays != pays:
            self.add_error('province', "Cette province n'appartient pas au pays sélectionné")

        stock       = cleaned_data.get('stock')
        stock_alerte = cleaned_data.get('stock_alerte')
        if stock is not None and stock_alerte is not None:
            if stock_alerte > stock:
                self.add_error('stock_alerte', "Le seuil d'alerte ne peut pas être supérieur au stock")

        return cleaned_data


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ['nom', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Informatique, Design, Marketing...'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description de la catégorie (optionnel)'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['nom'].widget.attrs.update({'autofocus': 'autofocus'})

    def clean_nom(self):
        nom = self.cleaned_data['nom']
        if self.user:
            qs = Categorie.objects.filter(user=self.user, nom=nom)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Cette catégorie existe déjà")
        return nom