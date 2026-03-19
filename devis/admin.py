from django.contrib import admin
from .models import Devis, LigneDevis

class LigneDevisInline(admin.TabularInline):
    model = LigneDevis
    extra = 1

@admin.register(Devis)
class DevisAdmin(admin.ModelAdmin):
    list_display = ['numero', 'client', 'statut', 'date_creation']
    list_filter = ['statut']
    inlines = [LigneDevisInline]