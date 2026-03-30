from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_factures, name='liste_factures'),
    path('ajouter/', views.ajouter_facture, name='ajouter_facture'),
    path('<int:pk>/', views.detail_facture, name='detail_facture'),
    path('<int:pk>/modifier/', views.modifier_facture, name='modifier_facture'),
    path('<int:pk>/supprimer/', views.supprimer_facture, name='supprimer_facture'),
    path('<int:pk>/statut/', views.changer_statut_facture, name='changer_statut_facture'),
    path('<int:pk>/pdf/', views.telecharger_pdf_facture, name='pdf_facture'),
    # factures/urls.py
    path('<int:pk>/liens/', views.gestion_liens_facture, name='gestion_liens_facture'),
    path('public/approbation/<str:token>/', views.visualiser_facture_approbation, name='visualiser_facture_approbation'),
    path('public/client/<str:token>/', views.visualiser_facture_client, name='visualiser_facture_client'),  
    

]