from django.urls import path
from . import views

urlpatterns = [
    path('inscription/',    views.inscription,    name='inscription'),
    path('connexion/',      views.connexion,      name='connexion'),
    path('deconnexion/',    views.deconnexion,    name='deconnexion'),
    path('profil/',         views.profil,         name='profil'),
    path('confidentialite/', views.politique_confidentialite, name='confidentialite'),


    # ── Activation email
    path('activer/<uidb64>/<token>/',
         views.activer_compte, name='activer_compte'),

    # ── Mot de passe oublié
    path('password-reset/',
         views.password_reset_request, name='password_reset'),
    path('password-reset/<uidb64>/<token>/',
         views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/succes/',
         views.password_reset_succes, name='password_reset_succes'),
]