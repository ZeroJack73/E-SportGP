import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from carrito.carrito import Carrito
from tienda.models import MovimientoInventario, Opinion, StockNegativo

from .models import ItemPedido, Pedido, Sucursal
from .servicios import cancelar_pedido, registrar_evento

POR_PAGINA = 10


class StockInsuficiente(Exception):
    pass


def _pedidos_de(usuario):
    items = ItemPedido.objects.select_related('producto', 'variante')
    return usuario.pedidos.select_related('sucursal').prefetch_related(Prefetch('items', queryset=items))


# --- Paso 1: Entrega -----------------------------------------------------

@login_required
def checkout(request):
    if request.user.is_staff:
        messages.info(request, 'Las cuentas de administración no pueden realizar compras.')
        return redirect('panel:inicio')
    carrito = Carrito(request)
    items = list(carrito)
    if not items:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('tienda:inicio')

    direcciones = list(request.user.direcciones.all())
    sucursales = list(Sucursal.objects.filter(activa=True))
    subtotal = carrito.total()

    if request.method == 'POST':
        metodo = request.POST.get('metodo_entrega')
        direccion = sucursal = None
        error = None
        if metodo == Pedido.Entrega.DOMICILIO:
            direccion = next((d for d in direcciones if str(d.pk) == request.POST.get('direccion')), None)
            if not direccion:
                error = 'Elige una dirección de entrega o agrega una nueva.'
        elif metodo == Pedido.Entrega.SUCURSAL:
            sucursal = next((s for s in sucursales if str(s.pk) == request.POST.get('sucursal')), None)
            if not sucursal:
                error = 'Elige la sucursal donde retirarás tu pedido.'
        else:
            error = 'Elige un método de entrega.'

        if error:
            messages.error(request, error)
            return redirect('pedidos:checkout')

        envio = Pedido.calcular_envio(subtotal, metodo)
        try:
            with transaction.atomic():
                pedido = Pedido(usuario=request.user, email=request.user.email, metodo_entrega=metodo,
                                subtotal=subtotal, envio=envio, total=subtotal + envio)
                if direccion:
                    pedido.direccion_alias = direccion.alias
                    pedido.recibe = direccion.recibe
                    pedido.telefono = direccion.telefono
                    pedido.direccion_texto = direccion.texto()
                else:
                    pedido.sucursal = sucursal
                    pedido.recibe = request.user.get_full_name()
                pedido.save()
                registrar_evento(pedido, request.user, 'Pedido creado por el cliente')
                for item in items:
                    # Reserva el stock solo si alcanza (bloquea la fila y deja el movimiento registrado)
                    try:
                        MovimientoInventario.registrar(
                            item['variante'].pk, MovimientoInventario.Tipo.VENTA, item['cantidad'],
                            'Venta en línea', usuario=request.user, referencia=pedido.codigo)
                    except StockNegativo:
                        raise StockInsuficiente(f"{item['producto'].nombre} ({item['variante'].descripcion})")
                    ItemPedido.objects.create(
                        pedido=pedido, producto=item['producto'], variante=item['variante'],
                        detalle_variante=item['variante'].descripcion,
                        precio=item['precio'], cantidad=item['cantidad'])
        except StockInsuficiente as e:
            messages.error(request, f'Ya no hay unidades suficientes de {e}. Ajusta tu carrito.')
            return redirect('carrito:detalle')

        carrito.limpiar()
        return redirect('pedidos:pasarela', codigo=pedido.codigo)

    predeterminada = next((d for d in direcciones if d.predeterminada), direcciones[0] if direcciones else None)
    return render(request, 'pedidos/checkout.html', {
        'items': items,
        'direcciones': direcciones,
        'direccion_sel': predeterminada,
        'direcciones_json': [{
            'id': d.pk, 'alias': d.alias, 'recibe': d.recibe, 'telefono': d.telefono,
            'linea1': d.linea1, 'linea2': d.linea2, 'predeterminada': d.predeterminada,
        } for d in direcciones],
        'sucursales': sucursales,
        'subtotal': subtotal,
        'envio_domicilio': Pedido.calcular_envio(subtotal, Pedido.Entrega.DOMICILIO),
        'unidades': len(carrito),
        'paso': 1,
    })


# --- Paso 2: Pasarela de pago (simulada) ---------------------------------

@login_required
def pasarela(request, codigo):
    """Pasarela de PRUEBAS. Sustituir por la integracion real (Stripe, PayPal, etc.).
    No solicita ni guarda datos de tarjeta."""
    pedido = get_object_or_404(Pedido, codigo=codigo, usuario=request.user)
    if pedido.estado != Pedido.Estado.PENDIENTE_PAGO:
        return redirect('pedidos:lista')

    if request.method == 'POST':
        if request.POST.get('resultado') == 'aprobar':
            pedido.marcar_pagado(referencia=f'PRUEBA-{secrets.token_hex(4).upper()}')
            registrar_evento(pedido, request.user, 'Pago en línea aprobado')
            _enviar_comprobante(request, pedido)
            return redirect('pedidos:confirmacion', codigo=pedido.codigo)
        messages.error(request, 'El pago fue rechazado. Puedes intentarlo de nuevo desde Mis pedidos.')
        return redirect(f"{reverse('pedidos:lista')}?pedido={pedido.codigo}")

    return render(request, 'pedidos/pasarela.html', {'pedido': pedido, 'paso': 2})


def _enviar_comprobante(request, pedido):
    cuerpo = render_to_string('pedidos/email/comprobante.txt', {
        'pedido': pedido,
        'url': request.build_absolute_uri(f"{reverse('pedidos:lista')}?pedido={pedido.codigo}"),
    })
    send_mail(f'SportPG - Pedido {pedido.codigo} confirmado', cuerpo, None, [pedido.email], fail_silently=True)


# --- Paso 3: Confirmacion ------------------------------------------------

@login_required
def confirmacion(request, codigo):
    pedido = get_object_or_404(_pedidos_de(request.user), codigo=codigo)
    if not pedido.pagado_en:
        return redirect('pedidos:lista')
    return render(request, 'pedidos/confirmacion.html', {'pedido': pedido, 'paso': 3})


# --- Mis pedidos ---------------------------------------------------------

@login_required
def mis_pedidos(request):
    pedidos = _pedidos_de(request.user)
    pagina = Paginator(pedidos, POR_PAGINA).get_page(request.GET.get('page'))

    seleccionado = None
    codigo = request.GET.get('pedido')
    if codigo:
        seleccionado = pedidos.filter(codigo=codigo).first()
    if seleccionado is None and pagina.object_list:
        seleccionado = pagina.object_list[0]

    calificables = []
    if seleccionado and seleccionado.estado == Pedido.Estado.ENTREGADO:
        ya = set(Opinion.objects.filter(usuario=request.user).values_list('producto_id', flat=True))
        vistos = set()
        for item in seleccionado.items.all():
            if item.producto_id not in vistos:
                vistos.add(item.producto_id)
                calificables.append({'item': item, 'calificado': item.producto_id in ya})

    return render(request, 'pedidos/lista.html', {
        'pedidos': pagina,
        'paginas': pagina.paginator.get_elided_page_range(pagina.number, on_each_side=1, on_ends=1),
        'sel': seleccionado,
        'calificables': calificables,
    })


@login_required
@require_POST
def cancelar(request, codigo):
    pedido = get_object_or_404(Pedido, codigo=codigo, usuario=request.user)
    destino = f"{reverse('pedidos:lista')}?pedido={pedido.codigo}"
    if not pedido.puede_cancelarse:
        messages.error(request, 'Este pedido ya no puede cancelarse.')
        return redirect(destino)

    reembolso = pedido.requiere_reembolso
    cancelar_pedido(pedido, request.user, 'Cancelado por el cliente')

    mensaje = f'Pedido {pedido.codigo} cancelado.'
    if reembolso:
        mensaje += ' El reembolso se realizará al método de pago original en 5 a 10 días hábiles.'
    messages.success(request, mensaje)
    return redirect(destino)


@login_required
@require_POST
def calificar(request, codigo):
    """Recibe la calificacion por fetch y responde JSON."""
    pedido = get_object_or_404(Pedido, codigo=codigo, usuario=request.user)
    if pedido.estado != Pedido.Estado.ENTREGADO:
        return JsonResponse({'ok': False, 'mensaje': 'Solo puedes calificar pedidos entregados.'}, status=400)

    item = pedido.items.filter(producto_id=request.POST.get('producto')).select_related('producto').first()
    if not item:
        return JsonResponse({'ok': False, 'mensaje': 'Ese producto no pertenece a este pedido.'}, status=400)
    try:
        nota = int(request.POST.get('calificacion', 0))
    except ValueError:
        nota = 0
    if not 1 <= nota <= 5:
        return JsonResponse({'ok': False, 'mensaje': 'Selecciona de 1 a 5 estrellas.'}, status=400)
    comentario = request.POST.get('comentario', '').strip()[:1000]

    u = request.user
    nombre = f'{u.first_name} {u.last_name[:1]}.' if u.last_name else (u.first_name or 'Cliente')
    Opinion.objects.update_or_create(
        producto=item.producto, usuario=u,
        defaults={'nombre': nombre, 'calificacion': nota, 'verificada': True,
                  'comentario': comentario or 'Sin comentario.'})
    return JsonResponse({'ok': True, 'mensaje': '¡Gracias por tu calificación!',
                         'producto': item.producto.nombre})
