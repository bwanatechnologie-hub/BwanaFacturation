from django import forms
from .models import Devis, LigneDevis
from clients.models import Client
from taxes.models import PaysTaxe
from produits.models import Produit


class DevisForm(forms.ModelForm):
    pays = forms.ChoiceField(
        choices=[],
        required=False,
        label="Pays / Taxe",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_pays_select'})
    )

    class Meta:
        model = Devis
        fields = ['client', 'date_validite', 'statut', 'notes',
                  'pays', 'type_taxe', 'taux_taxe']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'date_validite': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }, format='%Y-%m-%d'),  # ✅ Correction : format ajouté ici
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'type_taxe': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_type_taxe',
                'readonly': 'readonly'
            }),
            'taux_taxe': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'id_taux_taxe',
                'step': '0.01'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['client'].queryset = Client.objects.filter(utilisateur=user)

        # ✅ Champs optionnels — remplis automatiquement par le JS
        self.fields['taux_taxe'].required = False
        self.fields['type_taxe'].required = False
        self.fields['pays'].required = False

        # Choix des pays
        pays_choices = [('', '-- Sélectionner un pays --')]
        pays_choices += [
            (p.code, f"{p.nom} ({p.type_taxe} {p.taux_defaut}%)")
            for p in PaysTaxe.objects.filter(actif=True)
        ]
        self.fields['pays'].choices = pays_choices

    def clean_taux_taxe(self):
        """Retourner 0 si taux_taxe est vide"""
        taux = self.cleaned_data.get('taux_taxe')
        if taux is None or taux == '':
            return 0
        return taux

    def clean_type_taxe(self):
        """Retourner chaîne vide si type_taxe est vide"""
        return self.cleaned_data.get('type_taxe') or ''

    def clean_pays(self):
        """Retourner chaîne vide si pays est vide"""
        return self.cleaned_data.get('pays') or ''


class LigneDevisForm(forms.ModelForm):
    produit = forms.ModelChoiceField(
        queryset=Produit.objects.none(),
        required=False,
        label="Produit",
        widget=forms.Select(attrs={
            'class': 'form-select select-produit',
        })
    )

    class Meta:
        model = LigneDevis
        fields = ['description', 'quantite', 'prix_unitaire', 'tva']
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control description-input',
                'placeholder': 'Description du produit/service'
            }),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control quantite-input',
                'step': '0.01',
                'min': '0',
                'value': '1'
            }),
            'prix_unitaire': forms.NumberInput(attrs={
                'class': 'form-control prix-unitaire',
                'step': '0.01',
                'min': '0'
            }),
            'tva': forms.NumberInput(attrs={
                'class': 'form-control tva-input',
                'step': '0.01',
                'min': '0'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user:
            self.fields['produit'].queryset = Produit.objects.filter(
                user=user,
                actif=True
            ).select_related('pays', 'type_taxe').order_by('nom')
        else:
            self.fields['produit'].queryset = Produit.objects.none()

        self.fields['produit'].empty_label = "--- Sélectionnez un produit ---"

        if self.instance and self.instance.pk and self.instance.produit:
            self.fields['produit'].initial = self.instance.produit

    def save(self, commit=True):
        instance = super().save(commit=False)

        produit = self.cleaned_data.get('produit')
        if produit:
            instance.produit = produit
            if not instance.description:
                instance.description = produit.nom
            if not instance.prix_unitaire or instance.prix_unitaire == 0:
                instance.prix_unitaire = produit.prix_ht
            if not instance.tva or instance.tva == 0:
                instance.tva = produit.taux_tva

        if commit:
            instance.save()
        return instance


class BaseLigneDevisFormSet(forms.BaseFormSet):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['user'] = self.user
        return super()._construct_form(i, **kwargs)


# FormSet avec extra=1 pour création
LigneDevisFormSet = forms.formset_factory(
    LigneDevisForm,
    formset=BaseLigneDevisFormSet,
    extra=1,
    can_delete=True
)


class RechercheProduitForm(forms.Form):
    recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher un produit...',
            'id': 'search-produit'
        })
    )