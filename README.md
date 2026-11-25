# SportPG

E-commerce de artículos deportivos desarrollado en colaboración académica entre la UTP (Panamá) y la UVG (Guatemala), promoviendo la innovación tecnológica y el trabajo en equipo.

## Tecnologías

- Python + Django
- Bootstrap 5 y Bootstrap Icons
- SweetAlert2 (confirmaciones, errores, mensajes, guía de tallas, calificaciones)

## Estructura

| App       | Responsabilidad |
|-----------|-----------------|
| `tienda`  | Catálogo público con filtros, ficha de producto, variantes (talla + color con stock propio), galería y opiniones |
| `carrito` | Carrito en la sesión, por variante, paginado de 10 en 10 |
| `pedidos` | Checkout en 3 pasos (entrega, pago, confirmación), sucursales, mis pedidos, cancelación y calificación |
| `cuentas` | Registro e inicio de sesión por correo, recuperar contraseña, perfil y mis direcciones |
| `panel`   | Panel de administración: productos y categorías, inventario, gestión de pedidos y reportes |

## Instalación (Windows / PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_demo            # 18 productos de ejemplo con foto, variantes y opiniones
python manage.py cargar_clientes_demo   # sucursales + administrador y clienta de prueba con pedidos
python manage.py createsuperuser        # (opcional) otra cuenta de administración
python manage.py runserver
```

Abrir http://127.0.0.1:8000

**Cuentas de prueba (solo desarrollo):**

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@sportpg.com` | `AdminSportPG2026` |
| Cliente | `andrea@sportpg.com` | `SportPG2026` |

Ambos entran por el mismo login. Si la cuenta es de administración (`is_staff`) se abre el panel
`/panel/` y las compras quedan deshabilitadas para esa cuenta.

- El catálogo es público: se navega sin registrarse. Solo el checkout pide iniciar sesión.
- Se inicia sesión con el **correo**.
- Flujo de pedidos (panel > Pedidos): Pagado -> En preparación -> Enviado (domicilio, con registro de despacho) /
  Listo para retirar (sucursal) -> Entregado. Cada cambio queda en el historial y se avisa al cliente por correo.
- Inventario: todo cambio de stock (ventas, cancelaciones, entradas y salidas manuales) queda registrado con
  responsable y motivo. Nunca se permite stock negativo.
- `/admin/` (admin de Django) sigue disponible como respaldo para superusuarios.
- Los correos (comprobante de pago, recuperar contraseña) se imprimen en la consola del servidor.
- Envío: gratis desde `ENVIO_GRATIS_DESDE` USD; si no, `COSTO_ENVIO` (ver `config/settings.py`).
- Las fotos de ejemplo vienen de Pexels; ver `tienda/demo_img/CREDITOS.md`.

## Pago en línea

`pedidos/views.py -> pasarela` es una **pasarela de pruebas**: no pide datos de tarjeta, solo permite
simular un pago aprobado o rechazado. Para producción se reemplaza por la integración real
(Stripe, PayPal, etc.) que, al aprobar, debe llamar a `pedido.marcar_pagado(referencia)`.

## Uso de SweetAlert2 en las plantillas

- **Mensajes**: cualquier `messages.success/error/warning/info` de Django se muestra automáticamente.
- **Confirmaciones**: agregar `data-confirm="texto"` a un `<form>`. Opcionales: `data-confirm-title`, `data-confirm-icon`, `data-confirm-ok`, `data-confirm-color`.
- **Errores de formulario**: incluir `{% include 'includes/form_errores.html' %}` dentro del formulario.
- **Campos**: `{% load ui %}{% campo_simple form.email %}` (o `{% campo form.email 'bi-envelope' %}` con icono).
- **Botón con carga**: `data-loading="Texto"` en el botón de envío.
- **Cancelar con datos escritos**: `data-cancelar` en el enlace de cancelar.
- **Paginación**: `{% include 'includes/paginacion.html' with pagina=page_obj etiqueta="pedidos" %}`.

## Despliegue en Vercel + Supabase (gratis)

- **Vercel** ejecuta Django. Detecta `manage.py`, instala `requirements.txt`, usa Python 3.13 (`.python-version`)
  y corre `build.py` en cada despliegue (`pyproject.toml > [tool.vercel.scripts]`).
- **Supabase** guarda la base de datos (PostgreSQL) y las imágenes (Storage, bucket público).
- En tu computadora todo sigue igual: sin variables de entorno se usa SQLite e imágenes en `media/`.

### 1. Supabase

1. **New project** -> nombre `sportpg`, una **contraseña de base de datos solo con letras y números**
   (guárdala) y la región más cercana. Espera a que termine de crearse.
2. **Connect** (botón superior) -> *Connection string* -> tipo **URI** -> **Transaction pooler** (puerto **6543**).
   Copia la cadena y reemplaza `[YOUR-PASSWORD]` por tu contraseña. Ese es tu `DATABASE_URL`.
3. **Storage -> New bucket** -> nombre `media` -> activa **Public bucket** -> *Create*.
4. **Storage -> S3 (Configuration / Settings)** -> verifica que el protocolo S3 esté activado y anota la **Region**
   (y el **Endpoint**). En *Access keys* -> **New access key** -> copia el **Access key ID** y el **Secret access key**
   (el secreto se muestra una sola vez).
5. **Project Settings -> Data API / API** -> copia la **Project URL** (`https://xxxx.supabase.co`).

### 2. Claves secretas

En la terminal del proyecto genera dos valores aleatorios:

```powershell
.\venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY
.\venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(24))"   # CRON_SECRET
```

### 3. Subir el código a GitHub

```powershell
git add .
git commit -m "Preparar despliegue en Vercel + Supabase"
git push origin main
```

### 4. Vercel

1. **Add New -> Project** -> importa el repositorio de GitHub.
2. Framework: **Django** (lo detecta solo). Root Directory: `./`.
   **No cambies Build Command ni Install Command** (si se cambian, Vercel deja de ejecutar `build.py`).
3. Abre **Environment Variables** y agrega (para *Production* y *Preview*):

   | Variable | Valor |
   |---|---|
   | `DJANGO_DEBUG` | `0` |
   | `DJANGO_SECRET_KEY` | el primer valor generado |
   | `DATABASE_URL` | la cadena del *Transaction pooler* (paso 1.2) |
   | `SUPABASE_URL` | la Project URL (paso 1.5) |
   | `SUPABASE_STORAGE_BUCKET` | `media` |
   | `SUPABASE_S3_REGION` | la región de Storage > S3 |
   | `SUPABASE_S3_ENDPOINT` | el Endpoint de Storage > S3 (opcional) |
   | `SUPABASE_S3_ACCESS_KEY_ID` | Access key ID |
   | `SUPABASE_S3_SECRET_ACCESS_KEY` | Secret access key |
   | `DJANGO_ADMIN_EMAIL` | tu correo de administrador |
   | `DJANGO_ADMIN_PASSWORD` | una contraseña segura |
   | `CARGAR_DEMO` | `1` (catálogo de ejemplo en el primer despliegue) |
   | `CRON_SECRET` | el segundo valor generado |

4. **Deploy**. En los *Build Logs* deben aparecer `python manage.py migrate`, `Administrador creado`
   y `Datos de ejemplo cargados (18 productos nuevos)`.
5. Abre `https://<tu-proyecto>.vercel.app` e inicia sesión con tu correo de administrador: se abre `/panel/`.
6. Después del primer despliegue cambia `CARGAR_DEMO` a `0` (Settings -> Environment Variables) para que
   los productos de ejemplo que borres no vuelvan a crearse en el siguiente despliegue.
7. En **Settings -> Cron Jobs** debe aparecer `/salud/` una vez al día: mantiene activa la base de Supabase
   (los proyectos gratis se pausan tras una semana sin actividad).

Cada `git push` a `main` vuelve a desplegar. Las ramas generan vistas previas que **no** tocan la base de datos.

### Si algo falla

| Síntoma | Causa probable |
|---|---|
| El build falla con `ImproperlyConfigured: Falta la variable...` | Falta esa variable en Vercel (revisa también el entorno *Preview*). |
| Error de conexión a la base | Usa la cadena del **Transaction pooler** (puerto 6543), no la conexión directa, y revisa la contraseña. |
| Las fotos no se ven | El bucket `media` no es público, o las claves/región S3 no coinciden. |
| `Bad Request (400)` con un dominio propio | Agrega el dominio en `DJANGO_ALLOWED_HOSTS`. |
| Error 500 sin detalles | Revisa la pestaña **Logs** del proyecto; para ver el detalle pon `DJANGO_DEBUG=1`, vuelve a desplegar y luego regrésalo a `0`. |
| Subir una imagen falla | Máximo 4 MB por imagen (Vercel acepta peticiones de hasta 4.5 MB). |

Los correos (comprobantes y avisos) se escriben en la pestaña **Logs** de Vercel; no se envían a los clientes.
