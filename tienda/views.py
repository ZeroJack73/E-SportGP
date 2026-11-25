from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from carrito.carrito import Carrito

from .guias import guia_para
from .models import Categoria, Color, Deporte, Marca, Producto, Talla

ORDENES = {
    '': ('Recomendados', ['-destacado', '-creado']),
    'nuevos': ('Más nuevos', ['-es_nuevo', '-creado']),
    'precio_asc': ('Precio: menor a mayor', ['precio']),
    'precio_desc': ('Precio: mayor a menor', ['-precio']),
    'nombre': ('Nombre: A-Z', ['nombre']),
}
POR_PAGINA = 9


def _decimal(valor):
    try:
        return Decimal(valor) if valor not in (None, '') else None
    except InvalidOperation:
        return None


def catalogo(request):
    """Catalogo publico: no requiere iniciar sesion."""
    g = request.GET
    productos = (Producto.objects.filter(disponible=True).con_stock()
                 .select_related('deporte', 'categoria', 'marca'))

    sel = {
        'deporte': g.getlist('deporte'),
        'marca': g.getlist('marca'),
        'talla': g.getlist('talla'),
        'color': g.getlist('color'),
    }
    categoria = g.get('categoria', '')
    q = g.get('q', '').strip()
    precio_min, precio_max = _decimal(g.get('precio_min')), _decimal(g.get('precio_max'))
    solo_disponibles = g.get('disponibles') == '1'
    orden = g.get('orden', '') if g.get('orden', '') in ORDENES else ''

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(descripcion__icontains=q) |
            Q(marca__nombre__icontains=q) | Q(deporte__nombre__icontains=q))
    if sel['deporte']:
        productos = productos.filter(deporte__slug__in=sel['deporte'])
    if categoria:
        productos = productos.filter(categoria__slug=categoria)
    if sel['marca']:
        productos = productos.filter(marca__slug__in=sel['marca'])
    # Talla y color se evaluan sobre la MISMA variante (ej. talla 27 en color Negro)
    filtro_variante = {}
    if sel['talla']:
        filtro_variante['variantes__talla__nombre__in'] = sel['talla']
    if sel['color']:
        filtro_variante['variantes__color__nombre__in'] = sel['color']
    if filtro_variante:
        productos = productos.filter(**filtro_variante)
    if precio_min is not None:
        productos = productos.filter(precio__gte=precio_min)
    if precio_max is not None:
        productos = productos.filter(precio__lte=precio_max)
    if solo_disponibles:
        productos = productos.filter(stock_total__gt=0)

    productos = productos.distinct().order_by(*ORDENES[orden][1])
    paginator = Paginator(productos, POR_PAGINA)
    pagina = paginator.get_page(g.get('page'))

    hay_filtros = any(sel.values()) or categoria or q or precio_min or precio_max or solo_disponibles
    deporte_titulo = None
    if len(sel['deporte']) == 1:
        deporte_titulo = Deporte.objects.filter(slug=sel['deporte'][0]).first()

    return render(request, 'tienda/catalogo.html', {
        'productos': pagina,
        'paginas': paginator.get_elided_page_range(pagina.number, on_each_side=1, on_ends=1),
        'total': paginator.count,
        'deportes': Deporte.objects.all(),
        'categorias': Categoria.objects.all(),
        'marcas': Marca.objects.all(),
        'tallas': Talla.objects.all(),
        'colores': Color.objects.all(),
        'sel': sel,
        'categoria_sel': categoria,
        'q': q,
        'precio_min': g.get('precio_min', ''),
        'precio_max': g.get('precio_max', ''),
        'solo_disponibles': solo_disponibles,
        'orden': orden,
        'ordenes': [(k, v[0]) for k, v in ORDENES.items()],
        'hay_filtros': hay_filtros,
        'deporte_titulo': deporte_titulo,
    })


def detalle_producto(request, slug):
    producto = get_object_or_404(
        Producto.objects.select_related('deporte', 'categoria', 'marca'), slug=slug, disponible=True)
    variantes = list(producto.variantes.select_related('talla', 'color'))

    tallas, colores = [], []
    for v in variantes:
        if v.talla and v.talla not in tallas:
            tallas.append(v.talla)
        if v.color and v.color not in colores:
            colores.append(v.color)
    tallas.sort(key=lambda t: t.orden)
    colores.sort(key=lambda c: c.orden)

    carrito = Carrito(request)
    datos_variantes = [{
        'id': v.id,
        'talla': v.talla.nombre if v.talla else None,
        'color': v.color.nombre if v.color else None,
        'stock': v.stock,
        'en_carrito': carrito.cantidad_de(v),
    } for v in variantes]

    es_calzado = bool(tallas) and tallas[0].grupo == Talla.Grupo.CALZADO
    relacionados = (Producto.objects.filter(deporte=producto.deporte, disponible=True).con_stock()
                    .select_related('deporte', 'marca').exclude(pk=producto.pk)[:3])

    # "Volver al catalogo" respeta los filtros si se viene del catalogo
    volver = reverse('tienda:inicio')
    ref = request.META.get('HTTP_REFERER', '')
    if ref and url_has_allowed_host_and_scheme(ref, allowed_hosts={request.get_host()}):
        if urlparse(ref).path in (reverse('tienda:inicio'), reverse('tienda:lista')):
            volver = ref

    return render(request, 'tienda/detalle.html', {
        'producto': producto,
        'galeria': producto.galeria(),
        'tallas': tallas,
        'colores': colores,
        'es_calzado': es_calzado,
        'variantes_json': datos_variantes,
        'guia': guia_para(producto, tallas),
        'opiniones': producto.opiniones.all()[:10],
        'resumen': producto.resumen_opiniones(),
        'relacionados': relacionados,
        'volver': volver,
        'envio_gratis_desde': settings.ENVIO_GRATIS_DESDE,
    })


def salud(request):
    """Lo llama la tarea diaria de Vercel (vercel.json > crons) para mantener activa la base
    de Supabase: los proyectos gratis se pausan tras una semana sin actividad."""
    secreto = settings.CRON_SECRET
    if secreto and request.headers.get('Authorization') != f'Bearer {secreto}':
        return JsonResponse({'ok': False}, status=401)
    return JsonResponse({'ok': True, 'deportes': Deporte.objects.count()})
