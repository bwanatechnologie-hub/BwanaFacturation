from pathlib import Path
import os
from dotenv import load_dotenv
from django.contrib.messages import constants as messages

# Charger le fichier .env
load_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# ══════════════════════════════════════════
# SÉCURITÉ
# ══════════════════════════════════════════
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-ij+$)-5x_aq7_jjjtvur-%mjegs4k*%4++1)&!)%9+v1f%p8^r'
)
DEBUG         = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost,*').split(',')

# ══════════════════════════════════════════
# APPLICATIONS
# ══════════════════════════════════════════
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Nos applications
    'users',
    'clients',
    'devis',
    'factures',
    'taxes',
    'produits',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # ✅ Présent
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'users.admin_middleware.MaintenanceMiddleware',  # ← en dernier

]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ══════════════════════════════════════════
# BASE DE DONNÉES
# ══════════════════════════════════════════
DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     os.environ.get('DB_NAME',     'gestion_df'),
        'USER':     os.environ.get('DB_USER',     'admis_pdf'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'root'),
        'HOST':     os.environ.get('DB_HOST',     'localhost'),
        'PORT':     os.environ.get('DB_PORT',     '5432'),
    }
}

# ══════════════════════════════════════════
# VALIDATION MOT DE PASSE
# ══════════════════════════════════════════
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ══════════════════════════════════════════
# INTERNATIONALISATION
# ══════════════════════════════════════════
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE     = 'Africa/Ouagadougou'
USE_I18N      = True
USE_TZ        = True

# ══════════════════════════════════════════
# FICHIERS STATIQUES & MEDIA
# ══════════════════════════════════════════
STATIC_URL       = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT      = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL  = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ══════════════════════════════════════════
# AUTHENTIFICATION
# ══════════════════════════════════════════
LOGIN_URL             = '/users/connexion/'
LOGIN_REDIRECT_URL    = '/devis/'
LOGOUT_REDIRECT_URL   = '/users/connexion/'

# ══════════════════════════════════════════
# SESSIONS
# ══════════════════════════════════════════
SESSION_COOKIE_AGE          = 3600   # 1 heure
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST  = True

# ══════════════════════════════════════════
# MESSAGES BOOTSTRAP
# ══════════════════════════════════════════
MESSAGE_TAGS = {
    messages.DEBUG:   'secondary',
    messages.INFO:    'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR:   'danger',
}

# ══════════════════════════════════════════
# EMAIL GMAIL
# ══════════════════════════════════════════
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.environ.get(
    'EMAIL_HOST_USER', 'noreply@bwanafacturation.com'
)

# ══════════════════════════════════════════
# CSRF & SÉCURITÉ (AJOUTS)
# ══════════════════════════════════════════
CSRF_COOKIE_SECURE = False          # True en production (HTTPS)
CSRF_COOKIE_HTTPONLY = False        # Permet au JavaScript de lire le cookie
CSRF_COOKIE_SAMESITE = 'Lax'        # Protection contre les attaques CSRF
CSRF_USE_SESSIONS = False           # Utilise les cookies au lieu des sessions
CSRF_COOKIE_NAME = 'csrftoken'      # Nom du cookie (par défaut)
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN' # Nom de l'en-tête pour AJAX

# Sécurité des sessions
SESSION_COOKIE_SECURE = False        # True en production (HTTPS)
SESSION_COOKIE_HTTPONLY = True       # Empêche l'accès JavaScript aux cookies de session
SESSION_COOKIE_SAMESITE = 'Lax'      # Protection contre les attaques CSRF

# Sécurité supplémentaire (optionnel)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
]

# ══════════════════════════════════════════
# SITE
# ══════════════════════════════════════════
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')