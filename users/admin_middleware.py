from django.shortcuts import render
from django.urls import reverse


class MaintenanceMiddleware:
    """
    Redirige vers la page maintenance si le mode est activé.
    Les superusers et la page de connexion restent accessibles.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Importer ici pour éviter les imports circulaires
        try:
            from users.admin_models import MaintenanceMode
            maintenance = MaintenanceMode.get_instance()

            if maintenance.actif:
                # Toujours laisser passer les superusers
                if request.user.is_authenticated and request.user.is_superuser:
                    pass
                # Laisser passer la page de connexion et admin Django
                elif request.path in [
                    reverse('connexion'),
                    '/admin/',
                    '/admin-bwana/',
                ] or request.path.startswith('/admin/'):
                    pass
                else:
                    return render(request, 'admin_bwana/maintenance.html', {
                        'message': maintenance.message,
                        'date_fin': maintenance.date_fin,
                    }, status=503)
        except Exception:
            pass

        return self.get_response(request)