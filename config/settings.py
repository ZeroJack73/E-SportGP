"""
Configuracion de Django para SportPG.

- En tu computadora: SQLite + imagenes en media/ (sin variables de entorno).
- En Vercel: base de datos e imagenes en Supabase, configuradas con variables de entorno.
  Ver .env.example y la seccion "Despliegue en Vercel + Supabase" del README.
"""

import os
from pathlib import Path

from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# En local se pueden poner variables en un archivo .env (no se sube a git).
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass


def env_bool(nombre, por_defecto=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in ('1', 'true', 'yes', 'si', 'on')


def env_lista(nombre):
    return [x.strip() for x in os.environ.get(nombre, '').split(',') if x.strip()]


# Vercel define VERCEL=1 durante el build y en ejecucion
EN_VERCEL = os.environ.get('VERCEL') == '1'

# Local: DEBUG activo. Vercel: apagado (se puede forzar con DJANGO_DEBUG=1 para diagnosticar).
DEBUG = env_bool('DJANGO_DEBUG', por_defecto=not EN_VERCEL)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Falta la variable de entorno DJANGO_SECRET_KEY.')
    SECRET_KEY = 'django-insecure-solo-para-desarrollo-local'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.vercel.app'] + env_lista('DJANGO_ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app'] + [
    f'https://{h.lstrip(".")}' for h in env_lista('DJANGO_ALLOWED_HOSTS')]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    # Apps del proyecto
    'tienda',
    'carrito',
    'pedidos',
    'cuentas',
    'panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'carrito.context_processors.carrito',
                'tienda.context_processors.categorias',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Base de datos
# Sin DATABASE_URL: SQLite local. En Vercel: Supabase, usando el connection pooler
# en modo transaccion (puerto 6543), recomendado para funciones serverless.

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url

    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=0, ssl_require=True)}
    # El pooler en modo transaccion no admite cursores del lado del servidor ni
    # sentencias preparadas que sobrevivan entre transacciones.
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
    DATABASES['default'].setdefault('OPTIONS', {})['prepare_threshold'] = None
elif EN_VERCEL:
    raise ImproperlyConfigured('Falta la variable de entorno DATABASE_URL (Supabase).')
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internacionalizacion

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Panama'
USE_I18N = True
USE_TZ = True


# Archivos estaticos (CSS, JS, iconos propios)
# Vercel ejecuta collectstatic automaticamente porque STATIC_ROOT esta definido.

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Imagenes subidas (productos)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')        # https://<proyecto>.supabase.co
SUPABASE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'media')
SUPABASE_S3_KEY = os.environ.get('SUPABASE_S3_ACCESS_KEY_ID')
SUPABASE_S3_SECRET = os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY')
SUPABASE_S3_REGION = os.environ.get('SUPABASE_S3_REGION', 'us-east-1')

if SUPABASE_URL and SUPABASE_S3_KEY and SUPABASE_S3_SECRET:
    # Supabase Storage mediante su API compatible con S3, en un bucket PUBLICO
    _dominio = SUPABASE_URL.split('://', 1)[-1]
    STORAGE_ARCHIVOS = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            # Si Supabase muestra otro "Endpoint" en Storage > S3, ponlo en SUPABASE_S3_ENDPOINT
            'endpoint_url': os.environ.get('SUPABASE_S3_ENDPOINT') or f'{SUPABASE_URL}/storage/v1/s3',
            'region_name': SUPABASE_S3_REGION,
            'access_key': SUPABASE_S3_KEY,
            'secret_key': SUPABASE_S3_SECRET,
            'bucket_name': SUPABASE_BUCKET,
            'addressing_style': 'path',
            'signature_version': 's3v4',
            'file_overwrite': False,      # si se repite un nombre, se genera uno nuevo
            'querystring_auth': False,    # URLs publicas, sin firma
            'default_acl': None,
            # URL publica: https://<proyecto>.supabase.co/storage/v1/object/public/<bucket>/<archivo>
            'custom_domain': f'{_dominio}/storage/v1/object/public/{SUPABASE_BUCKET}',
            'url_protocol': 'https:',
        },
    }
elif EN_VERCEL:
    raise ImproperlyConfigured('Faltan las variables de Supabase Storage (SUPABASE_URL y claves S3).')
else:
    STORAGE_ARCHIVOS = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}

STORAGES = {
    'default': STORAGE_ARCHIVOS,
    'staticfiles': {
        'BACKEND': ('django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
                    else 'whitenoise.storage.CompressedManifestStaticFilesStorage'),
    },
}

# Tamano maximo por imagen subida desde el panel (Vercel acepta peticiones de hasta 4.5 MB)
MAX_IMAGEN_MB = 4


# Autenticacion (correo electronico o usuario)
AUTHENTICATION_BACKENDS = [
    'cuentas.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]
LOGIN_URL = 'cuentas:login'
LOGIN_REDIRECT_URL = 'tienda:inicio'
LOGOUT_REDIRECT_URL = 'tienda:inicio'

# Carrito en sesion
CARRITO_SESSION_ID = 'carrito'

# Envio
ENVIO_GRATIS_DESDE = 100      # USD
COSTO_ENVIO = '5.00'          # USD, si no aplica envio gratis

# Tarea diaria de Vercel que evita que Supabase pause el proyecto por inactividad
CRON_SECRET = os.environ.get('CRON_SECRET', '')

# Mensajes con clases compatibles con SweetAlert2
MESSAGE_TAGS = {
    messages.DEBUG: 'info',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'error',
}


# Correo
# Los correos (comprobantes, avisos, recuperar contrasena) se escriben en el registro
# del servidor (en Vercel: pestana Logs). Para enviarlos de verdad, configura un proveedor SMTP.

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}
SILENCED_SYSTEM_CHECKS = ['mail.E001']  # correo de consola a proposito (ver arriba)


# Seguridad en produccion (Vercel sirve todo por HTTPS detras de su proxy)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'

# Errores y correos visibles en los logs (en Vercel: pestana Logs del proyecto)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}
