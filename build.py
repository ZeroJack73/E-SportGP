"""
Paso de build en Vercel (declarado en pyproject.toml > [tool.vercel.scripts]).

Se ejecuta despues de instalar dependencias y antes de publicar:
  1. Aplica las migraciones en la base de Supabase.
  2. Crea la cuenta de administracion con DJANGO_ADMIN_EMAIL / DJANGO_ADMIN_PASSWORD (si no existe).
  3. Si CARGAR_DEMO=1, carga el catalogo de ejemplo (sube las fotos a Supabase Storage),
     las sucursales y la clienta de prueba. Es seguro repetirlo: no duplica datos.
  4. Reune los archivos estaticos.

Los pasos 1 a 3 solo corren en el despliegue de PRODUCCION, para que las vistas previas
(otras ramas) no modifiquen la base de datos real.
"""
import os
import subprocess
import sys


def manage(*args):
    print(f'> python manage.py {" ".join(args)}', flush=True)
    subprocess.run([sys.executable, 'manage.py', *args], check=True)


def crear_admin():
    email = os.environ.get('DJANGO_ADMIN_EMAIL', '').strip().lower()
    password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')
    if not email or not password:
        print('DJANGO_ADMIN_EMAIL / DJANGO_ADMIN_PASSWORD no definidos: no se crea administrador.')
        return
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if User.objects.filter(email__iexact=email).exists():
        print(f'El administrador {email} ya existe.')
        return
    User.objects.create_superuser(username=email, email=email, password=password,
                                  first_name='Administrador', last_name='SportPG')
    print(f'Administrador creado: {email}')


def main():
    entorno = os.environ.get('VERCEL_ENV', 'production')
    if entorno == 'production':
        manage('migrate', '--noinput')
        crear_admin()
        if os.environ.get('CARGAR_DEMO') == '1':
            manage('cargar_demo')
            manage('cargar_clientes_demo', '--sin-admin')
    else:
        print(f'Despliegue "{entorno}": se omiten migraciones y datos de ejemplo.')
    manage('collectstatic', '--noinput')


if __name__ == '__main__':
    main()
