# clients/forms.py
from django import forms
from .models import Client
# ✅ IMPORTANT: Importer Pays depuis taxes.models
from taxes.models import Pays  # ← Changement clé !
# ❌ Supprimer: from produits.models import Pays


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'nom', 'prenom', 'email',
            'indicatif', 'telephone',
            'pays_obj',              # ✅ pays_obj (ForeignKey vers taxes.models.Pays)
            'province', 'ville', 'code_postal',
            'adresse', 'entreprise', 'logo',
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du client'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'indicatif': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_indicatif'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'XX XX XX XX',
                'id': 'id_telephone'
            }),
            'pays_obj': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_pays_obj'
            }),
            'province': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Province / État / Région',
            }),
            'ville': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ville'
            }),
            'code_postal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code postal'
            }),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Adresse complète'
            }),
            'entreprise': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Nom de l'entreprise"
            }),
            'logo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ✅ Utiliser Pays.objects depuis taxes.models
        self.fields['pays_obj'].queryset = Pays.objects.filter(actif=True).order_by('nom')
        self.fields['pays_obj'].empty_label = '-- Sélectionnez un pays --'

        # Champs optionnels
        for field in ['prenom', 'email', 'telephone', 'province',
                      'ville', 'code_postal', 'adresse', 'entreprise', 'logo']:
            self.fields[field].required = False

    def clean(self):
        """Validation personnalisée"""
        cleaned_data = super().clean()
        
        # Vérifier que le pays sélectionné existe
        pays = cleaned_data.get('pays_obj')
        if pays and not pays.actif:
            self.add_error('pays_obj', 'Ce pays n\'est pas actif.')
        
        return cleaned_data