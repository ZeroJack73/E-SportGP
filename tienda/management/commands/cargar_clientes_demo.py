from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cuentas.models import Direccion, Perfil
from pedidos.models import EventoPedido, ItemPedido, Pedido, Sucursal
from tienda.models import Variante

SUCURSALES = [
    ('Sucursal Tumba Muerto', 'Av. Ricardo J. Alfaro, Panamá', 'Lun a sáb, 9:00 a 19:00'),
    ('Sucursal Costa del Este', 'Av. Centenario, Costa del Este, Panamá', 'Lun a dom, 10:00 a 20:00'),
]

EMAIL = 'andrea@sportpg.com'
PASSWORD = 'SportPG2026'
ADMIN_EMAIL = 'admin@sportpg.com'
ADMIN_PASSWORD = 'AdminSportPG2026'

# (dias atras, estado, entrega, [(producto, talla, color, cantidad)])
PEDIDOS = [
    (0, 'pagado', 'domicilio', [('Tenis Running Velocity Pro', '27', 'Lima', 1), ('Top deportivo Flow', 'M', 'Negro', 2)]),
    (3, 'en_preparacion', 'domicilio', [('Kettlebell 12 kg', None, 'Negro', 1)]),
    (5, 'enviado', 'domicilio', [('Balón de fútbol Match 5', None, 'Blanco', 1), ('Botella deportiva 750 ml', None, 'Azul', 1)]),
    (7, 'listo_retiro', 'sucursal', [('Casco MTB Enduro', 'L', 'Naranja', 1)]),
    (12, 'entregado', 'domicilio', [('Tenis Running Velocity Pro', '26', 'Negro', 1), ('Shaker de proteína 600 ml', None, 'Gris', 1)]),
]


class Command(BaseCommand):
    help = 'Crea sucursales y una clienta de prueba con direcciones y pedidos en distintos estados.'

    def add_arguments(self, parser):
        parser.add_argument('--sin-admin', action='store_true',
                            help='No crear la cuenta admin@sportpg.com (en producción se usa DJANGO_ADMIN_EMAIL).')

    @transaction.atomic
    def handle(self, *args, **options):
        for nombre, direccion, horario in SUCURSALES:
            Sucursal.objects.get_or_create(nombre=nombre, defaults={'direccion': direccion, 'horario': horario})

        if not options['sin_admin'] and not User.objects.filter(email=ADMIN_EMAIL).exists():
            User.objects.create_superuser(username=ADMIN_EMAIL, email=ADMIN_EMAIL, password=ADMIN_PASSWORD,
                                          first_name='Administrador', last_name='SportPG')
            self.stdout.write(self.style.SUCCESS(f'Administrador creado: {ADMIN_EMAIL} / {ADMIN_PASSWORD}'))

        if User.objects.filter(email=EMAIL).exists():
            self.stdout.write('La clienta de prueba ya existe; no se modificó.')
            return

        u = User.objects.create_user(username=EMAIL, email=EMAIL, password=PASSWORD,
                                     first_name='Andrea', last_name='Martínez')
        Perfil.objects.create(usuario=u, telefono='+50761234567', acepto_terminos=timezone.now())
        casa = Direccion.objects.create(
            usuario=u, alias='Casa', recibe='Andrea Martínez', telefono='+50761234567',
            calle='Vía Argentina, PH El Cangrejo', apto='4B', corregimiento='Bella Vista',
            distrito='Panamá', provincia='Panamá', codigo_postal='0801', predeterminada=True)
        Direccion.objects.create(
            usuario=u, alias='Oficina', recibe='Andrea Martínez', telefono='+50761234567',
            calle='Calle 50, Torre Global Plaza', apto='Piso 3', corregimiento='Bella Vista',
            distrito='Panamá', provincia='Panamá')
        sucursal = Sucursal.objects.first()

        ahora = timezone.now()
        for dias, estado, entrega, lineas in reversed(PEDIDOS):
            pedido = Pedido(usuario=u, email=EMAIL, estado=estado, metodo_entrega=entrega,
                            recibe=casa.recibe, telefono=casa.telefono)
            if entrega == 'domicilio':
                pedido.direccion_alias, pedido.direccion_texto = casa.alias, casa.texto()
            else:
                pedido.sucursal = sucursal
            pedido.save()
            subtotal = 0
            for nombre, talla, color, cantidad in lineas:
                v = Variante.objects.select_related('producto').get(
                    producto__nombre=nombre, talla__nombre=talla, color__nombre=color)
                ItemPedido.objects.create(pedido=pedido, producto=v.producto, variante=v,
                                          detalle_variante=v.descripcion, precio=v.producto.precio,
                                          cantidad=cantidad)
                subtotal += v.producto.precio * cantidad
            envio = Pedido.calcular_envio(subtotal, entrega)
            fecha = ahora - timedelta(days=dias)
            flujo = ['pagado', 'en_preparacion', 'enviado' if entrega == 'domicilio' else 'listo_retiro', 'entregado']
            for paso, est in enumerate(flujo[:flujo.index(estado) + 1]):
                ev = EventoPedido.objects.create(pedido=pedido, estado=est, nota='Datos de ejemplo')
                EventoPedido.objects.filter(pk=ev.pk).update(creado=fecha + timedelta(days=paso))
            extra = {}
            if estado in ('enviado', 'entregado') and entrega == 'domicilio':
                extra = {'numero_guia': f'SP-GUIA-{pedido.pk:05d}', 'bultos': 1, 'peso_kg': 1.2,
                         'despachado_en': fecha + timedelta(days=2)}
            if estado == 'entregado':
                extra['entregado_en'] = fecha + timedelta(days=3)
            Pedido.objects.filter(pk=pedido.pk).update(
                subtotal=subtotal, envio=envio, total=subtotal + envio, creado=fecha,
                actualizado=fecha + timedelta(days=4 if estado == 'entregado' else 0),
                pagado_en=fecha, referencia_pago='PRUEBA-DEMO',
                entrega_desde=(fecha + timedelta(days=3)).date(), entrega_hasta=(fecha + timedelta(days=5)).date(),
                **extra)

        self.stdout.write(self.style.SUCCESS(f'Clienta de prueba creada: {EMAIL} / {PASSWORD}'))
