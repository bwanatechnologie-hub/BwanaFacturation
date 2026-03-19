from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.views.static import serve
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirection racine → dashboard
    path('', lambda request: redirect('/devis/tableau-de-bord/'), name='home'),

    path('users/',       include('users.urls')),
    path('clients/',     include('clients.urls')),
    path('devis/',       include('devis.urls')),
    path('factures/',    include('factures.urls')),
    path('api/',         include('taxes.urls')),
    path('produits/',    include('produits.urls')),

    # ✅ Administration personnalisée
    path('admin-bwana/', include('users.urls_admin')),

    # Media protégés par login
    path('media/<path:path>', login_required(serve), {
        'document_root': settings.MEDIA_ROOT
    }),
]