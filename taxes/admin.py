from django.contrib import admin
from .models import PaysTaxe

@admin.register(PaysTaxe)
class PaysTaxeAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'type_taxe', 'taux_defaut', 'actif']
    list_editable = ['taux_defaut', 'actif']
    search_fields = ['nom', 'code']
    ordering = ['nom']