from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from pedidos.models import Pedido
from tienda.models import Variante

from .carrito import Carrito
from .forms import CantidadForm


def _es_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _respuesta(request, ok, mensaje, extra=None, destino='carrito:detalle'):
    """Responde JSON (peticion fetch) o redirige con un mensaje (formulario normal)."""
    if _es_ajax(request):
        return JsonResponse({'ok': ok, 'mensaje': mensaje, **(extra or {})}, status=200 if ok else 400)
    (messages.success if ok else messages.error)(request, mensaje)
    return redirect(request.POST.get('next') or destino)


@require_POST
def agregar(request, variante_id):
    carrito = Carrito(request)
    variante = get_object_or_404(
        Variante.objects.select_related('producto', 'talla', 'color'),
        id=variante_id, producto__disponible=True)
    producto = variante.producto
    if request.user.is_staff:
        return _respuesta(request, False, 'Las cuentas de administración no pueden realizar compras.',
                          destino='panel:inicio')
    form = CantidadForm(request.POST)

    if not form.is_valid():
        errores = ' '.join(e for errs in form.errors.values() for e in errs)
        return _respuesta(request, False, errores)

    cantidad = form.cleaned_data['cantidad']
    reemplazar = form.cleaned_data['reemplazar']
    if variante.stock == 0:
        return _respuesta(request, False, f'"{producto.nombre}" está agotado en esta variante.')

    en_carrito = 0 if reemplazar else carrito.cantidad_de(variante)
    disponibles = variante.stock - en_carrito
    if cantidad > disponibles:
        if disponibles <= 0:
            msg = f'Ya tienes en tu carrito todas las unidades disponibles ({variante.stock}).'
        else:
            msg = f'Solo puedes agregar {disponibles} unidad{"es" if disponibles != 1 else ""} más.'
        return _respuesta(request, False, msg)

    carrito.agregar(variante, cantidad, reemplazar=reemplazar)
    mensaje = 'Cantidad actualizada.' if reemplazar else 'Producto agregado al carrito'
    return _respuesta(request, True, mensaje, {
        'producto': producto.nombre,
        'variante': variante.descripcion,
        'cantidad': cantidad,
        'total_items': len(carrito),
    })


@require_POST
def eliminar(request, variante_id):
    variante = get_object_or_404(Variante.objects.select_related('producto'), id=variante_id)
    Carrito(request).eliminar(variante)
    messages.success(request, f'"{variante.producto.nombre}" se eliminó del carrito.')
    return redirect('carrito:detalle')


@require_POST
def vaciar(request):
    Carrito(request).limpiar()
    messages.success(request, 'El carrito se vació correctamente.')
    return redirect('carrito:detalle')


POR_PAGINA = 10


def detalle(request):
    if request.user.is_staff:
        messages.info(request, 'Las cuentas de administración no tienen carrito de compras.')
        return redirect('panel:inicio')
    carrito = Carrito(request)
    items = list(carrito)
    pagina = Paginator(items, POR_PAGINA).get_page(request.GET.get('page'))
    subtotal = carrito.total()
    envio = Pedido.calcular_envio(subtotal, Pedido.Entrega.DOMICILIO)
    return render(request, 'carrito/detalle.html', {
        'items': pagina,
        'paginas': pagina.paginator.get_elided_page_range(pagina.number, on_each_side=1, on_ends=1),
        'subtotal': subtotal,
        'envio': envio,
        'total': subtotal + envio,
        'falta_envio_gratis': max(Decimal(settings.ENVIO_GRATIS_DESDE) - subtotal, Decimal('0')),
    })
