from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_devis, name='liste_devis'),
    path('ajouter/', views.ajouter_devis, name='ajouter_devis'),
    path('<int:pk>/', views.detail_devis, name='detail_devis'),
    path('<int:pk>/modifier/', views.modifier_devis, name='modifier_devis'),
    path('<int:pk>/supprimer/', views.supprimer_devis, name='supprimer_devis'),
    path('<int:pk>/transformer/', views.transformer_en_facture, name='transformer_en_facture'),
    path('<int:pk>/pdf/', views.telecharger_pdf_devis, name='pdf_devis'),
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord'),

]