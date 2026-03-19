from django.urls import path
from . import views

urlpatterns = [
    path('taxe/', views.get_taxe_pays, name='get_taxe_pays'),
    path('pays/', views.liste_pays_json, name='liste_pays_json'),
]