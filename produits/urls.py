from django.urls import path
from . import views

urlpatterns = [
    # Produits
    path('', views.liste_produits, name='liste_produits'),
    path('ajouter/', views.ajouter_produit, name='ajouter_produit'),
    path('<int:pk>/modifier/', views.modifier_produit, name='modifier_produit'),
    path('<int:pk>/supprimer/', views.supprimer_produit, name='supprimer_produit'),
    path('<int:pk>/dupliquer/', views.dupliquer_produit, name='dupliquer_produit'),
    path('api/provinces/', views.get_provinces_ajax, name='api_provinces'),
    path('api/types-taxe/', views.get_types_taxe_ajax, name='api_types_taxe'),
    path('api/taux-taxe/', views.get_taux_taxe_ajax, name='api_taux_taxe'),
    path('api/produit/<int:pk>/', views.get_produit_ajax, name='api_produit'),  # ← ajout
    path('unites/ajouter/', views.ajouter_unite_vente, name='ajouter_unite_vente'),
    # Catégories
    path('categories/', views.liste_categories, name='liste_categories'),
    path('categories/ajouter/', views.ajouter_categorie, name='ajouter_categorie'),
    path('categories/<int:pk>/modifier/', views.modifier_categorie, name='modifier_categorie'),
    path('categories/<int:pk>/supprimer/', views.supprimer_categorie, name='supprimer_categorie'),
]