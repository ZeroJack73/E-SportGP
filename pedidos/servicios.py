"""Operaciones de pedidos compartidas por la tienda y el panel de administracion."""
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from tienda.models import MovimientoInventario

from .models import EventoPedido, Pedido


def registrar_evento(pedido, usuario, nota=''):
    EventoPedido.objects.create(pedido=pedido, estado=pedido.estado, usuario=usuario, nota=nota)


@transaction.atomic
def cancelar_pedido(pedido, usuario, nota):
    """Cancela el pedido y devuelve el stock de cada articulo al inventario."""
    for item in pedido.items.all():
        if item.variante_id:
            MovimientoInventario.registrar(
                item.variante_id, MovimientoInventario.Tipo.DEVOLUCION, item.cantidad,
                'Cancelación de pedido', usuario=usuario, referencia=pedido.codigo)
    pedido.estado = Pedido.Estado.CANCELADO
    pedido.actualizado_por = usuario
    pedido.save()
    registrar_evento(pedido, usuario, nota)


@transaction.atomic
def cambiar_estado(pedido, nuevo, usuario, despacho=None):
    """Aplica un cambio de estado permitido por el flujo. despacho = dict(peso_kg, bultos, numero_guia)."""
    if nuevo == Pedido.Estado.CANCELADO:
        cancelar_pedido(pedido, usuario, 'Cancelado por administración')
        return
    pedido.estado = nuevo
    pedido.actualizado_por = usuario
    nota = ''
    if despacho:
        pedido.peso_kg = despacho['peso_kg']
        pedido.bultos = despacho['bultos']
        pedido.numero_guia = despacho['numero_guia']
        pedido.despachado_en = timezone.now()
        nota = f"Guía {despacho['numero_guia']} · {despacho['bultos']} bulto(s) · {despacho['peso_kg']} kg"
    if nuevo == Pedido.Estado.ENTREGADO:
        pedido.entregado_en = timezone.now()
    pedido.save()
    registrar_evento(pedido, usuario, nota)
    _notificar_cliente(pedido)


MENSAJES = {
    Pedido.Estado.EN_PREPARACION: 'Estamos preparando tu pedido.',
    Pedido.Estado.ENVIADO: 'Tu pedido va en camino.',
    Pedido.Estado.LISTO_RETIRO: 'Tu pedido está listo para retirar en sucursal.',
    Pedido.Estado.ENTREGADO: 'Tu pedido fue entregado. ¡Cuéntanos qué te pareció!',
}


def _notificar_cliente(pedido):
    texto = MENSAJES.get(pedido.estado)
    if not texto:
        return
    cuerpo = f'Hola {pedido.usuario.first_name or ""},\n\n{texto}\nPedido: {pedido.codigo}\n'
    if pedido.estado == Pedido.Estado.ENVIADO and pedido.numero_guia:
        cuerpo += f'Número de guía: {pedido.numero_guia}\n'
    if pedido.estado == Pedido.Estado.LISTO_RETIRO and pedido.sucursal:
        cuerpo += f'Sucursal: {pedido.sucursal.nombre} ({pedido.sucursal.direccion})\n'
    cuerpo += '\nEquipo SportPG'
    send_mail(f'SportPG - Pedido {pedido.codigo}: {pedido.get_estado_display()}', cuerpo, None,
              [pedido.email], fail_silently=True)
