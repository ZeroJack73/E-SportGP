import csv
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Max, ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from pedidos.models import Pedido
from pedidos.servicios import cambiar_estado
from tienda.models import (Categoria, Deporte, MovimientoInventario, Producto, ProductoImagen,
                           StockNegativo, Variante)

from .forms import (DespachoForm, FiltroPedidosForm, FiltroReporteForm, MovimientoForm,
                    NodoCategoriaForm, ProductoForm, VarianteFormSet)

POR_PAGINA = 10


def staff_requerido(vista):
    """Solo cuentas de administracion (is_staff). Si no hay sesion, manda al login."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse('cuentas:login'))
        if not request.user.is_staff:
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


def _paginar(request, qs):
    return Paginator(qs, POR_PAGINA).get_page(request.GET.get('page'))


@staff_requerido
def inicio(request):
    return redirect('panel:pedidos')


# --- Productos ---------------------------------------------------------------

@staff_requerido
def productos(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    qs = (Producto.objects.select_related('deporte', 'categoria', 'marca')
          .annotate(n_variantes=Count('variantes')).order_by('nombre'))
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(marca__nombre__icontains=q) |
                       Q(variantes__sku__icontains=q)).distinct()
    if request.GET.get('deporte', '').isdigit():
        qs = qs.filter(deporte_id=request.GET['deporte'])
    if request.GET.get('categoria', '').isdigit():
        qs = qs.filter(categoria_id=request.GET['categoria'])
    if estado == 'activo':
        qs = qs.filter(disponible=True)
    elif estado == 'inactivo':
        qs = qs.filter(disponible=False)
    return render(request, 'panel/productos.html', {
        'seccion': 'productos', 'tab': 'productos',
        'productos': _paginar(request, qs), 'q': q, 'estado': estado,
        'total_productos': Producto.objects.count(),
    })


SLOTS_EXTRA = [('imagen_frontal', 'quitar_frontal', 'Vista frontal', 1),
               ('imagen_detalle', 'quitar_detalle', 'Detalle', 2)]


@staff_requerido
def producto_form(request, pk=None):
    producto = get_object_or_404(Producto, pk=pk) if pk else None
    extras = {i.orden: i for i in producto.imagenes.all()} if producto else {}

    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        formset = VarianteFormSet(request.POST, instance=producto or Producto(), prefix='var')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                producto = form.save()
                formset.instance = producto
                formset.save()
                # Imagenes adicionales (Frontal / Detalle)
                for campo, quitar, etiqueta, orden in SLOTS_EXTRA:
                    archivo = form.cleaned_data.get(campo)
                    actual = extras.get(orden)
                    if archivo:
                        if actual:
                            actual.imagen.delete(save=False)
                            actual.imagen = archivo
                            actual.save()
                        else:
                            ProductoImagen.objects.create(producto=producto, imagen=archivo,
                                                          etiqueta=etiqueta, orden=orden)
                    elif actual and form.cleaned_data.get(quitar):
                        actual.imagen.delete(save=False)
                        actual.delete()
            messages.success(request, f'Producto "{producto.nombre}" guardado.')
            return redirect('panel:productos')
    else:
        form = ProductoForm(instance=producto)
        formset = VarianteFormSet(instance=producto or Producto(), prefix='var')

    errores = []
    for f in [form, *formset.forms]:
        for campo, lista in f.errors.items():
            etiqueta = f.fields[campo].label if campo in f.fields else ''
            errores += [f'{etiqueta}: {e}' if etiqueta else e for e in lista]
    errores += list(formset.non_form_errors())

    return render(request, 'panel/producto_form.html', {
        'seccion': 'productos', 'form': form, 'formset': formset, 'producto': producto,
        'extra_frontal': extras.get(1), 'extra_detalle': extras.get(2), 'errores': errores,
        'max_imagen_mb': settings.MAX_IMAGEN_MB,
    })


@staff_requerido
@require_POST
def producto_estado(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    producto.disponible = not producto.disponible
    producto.save(update_fields=['disponible'])
    messages.success(request, f'"{producto.nombre}" ahora está {"activo" if producto.disponible else "inactivo"}.')
    return redirect(request.POST.get('next') or 'panel:productos')


# --- Categorias ----------------------------------------------------------------

@staff_requerido
def categorias(request):
    deportes = Deporte.objects.annotate(n=Count('productos')).order_by('orden', 'nombre')
    por_deporte = defaultdict(list)
    filas = (Producto.objects.values('deporte_id', 'categoria_id', 'categoria__nombre')
             .annotate(n=Count('id')).order_by('categoria__nombre'))
    for f in filas:
        por_deporte[f['deporte_id']].append(f)
    arbol = [{'deporte': d, 'categorias': por_deporte.get(d.pk, [])} for d in deportes]
    cats = Categoria.objects.annotate(n=Count('productos')).order_by('nombre')
    return render(request, 'panel/categorias.html', {
        'seccion': 'categorias', 'tab': 'categorias', 'arbol': arbol, 'categorias': cats,
        'total_productos': Producto.objects.count(),
    })


@staff_requerido
@require_POST
def categoria_guardar(request):
    form = NodoCategoriaForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'mensaje': 'Revisa el nombre y el tipo.'}, status=400)
    cd = form.cleaned_data
    Modelo = Deporte if cd['tipo'] == 'deporte' else Categoria
    pk = request.POST.get('id')
    obj = get_object_or_404(Modelo, pk=pk) if pk else Modelo()
    if Modelo.objects.filter(nombre__iexact=cd['nombre']).exclude(pk=obj.pk).exists():
        return JsonResponse({'ok': False, 'mensaje': f'Ya existe "{cd["nombre"]}".'}, status=400)
    obj.nombre, obj.icono = cd['nombre'], cd['icono']
    if not pk:
        obj.slug = ''
    obj.save()
    messages.success(request, f'"{obj.nombre}" guardado.')
    return JsonResponse({'ok': True})


@staff_requerido
@require_POST
def categoria_eliminar(request, tipo, pk):
    Modelo = Deporte if tipo == 'deporte' else Categoria
    obj = get_object_or_404(Modelo, pk=pk)
    try:
        obj.delete()
        messages.success(request, f'"{obj.nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{obj.nombre}": tiene productos asociados.')
    return redirect('panel:categorias')


# --- Inventario ------------------------------------------------------------------

@staff_requerido
def inventario(request):
    q = request.GET.get('q', '').strip()
    disp = request.GET.get('disp', '')
    variantes = Variante.objects.select_related('producto', 'talla', 'color').order_by('producto__nombre', 'talla__orden', 'color__orden')
    agotadas = variantes.filter(stock=0).count()
    bajas = sum(1 for v in variantes.filter(stock__gt=0) if v.stock <= v.stock_minimo)
    qs = variantes
    if q:
        qs = qs.filter(Q(producto__nombre__icontains=q) | Q(sku__icontains=q) |
                       Q(talla__nombre__iexact=q) | Q(color__nombre__icontains=q))
    if disp == 'agotado':
        qs = qs.filter(stock=0)
    elif disp == 'bajo':
        qs = qs.filter(stock__gt=0, stock__lte=F('stock_minimo'))
    elif disp == 'normal':
        qs = qs.filter(stock__gt=F('stock_minimo'))

    form = MovimientoForm(request.POST or None, initial={'variante': request.GET.get('variante')})
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        try:
            with transaction.atomic():
                mov = MovimientoInventario.registrar(cd['variante'].pk, cd['tipo'], cd['cantidad'],
                                                     cd['motivo'], usuario=request.user)
        except StockNegativo:
            messages.error(request, 'El movimiento dejaría stock negativo. Revisa la cantidad.')
        else:
            signo = '+' if mov.es_entrada else '-'
            messages.success(request, f'{mov.variante.sku}: {signo}{mov.cantidad} unidades. Nuevo stock: {mov.stock_nuevo}.')
            return redirect(request.get_full_path())

    ultima = MovimientoInventario.objects.aggregate(u=Max('creado'))['u']
    return render(request, 'panel/inventario.html', {
        'seccion': 'inventario', 'variantes': _paginar(request, qs), 'q': q, 'disp': disp,
        'agotadas': agotadas, 'bajas': bajas, 'umbral': 5, 'ultima': ultima,
        'form': form, 'mostrar_form': request.method == 'POST' or 'registrar' in request.GET,
        'datos_variantes': {str(v.pk): {'sku': v.sku, 'stock': v.stock} for v in variantes},
    })


@staff_requerido
def historial_variante(request, pk):
    v = get_object_or_404(Variante.objects.select_related('producto', 'talla', 'color'), pk=pk)
    movs = v.movimientos.select_related('usuario')[:30]
    return JsonResponse({
        'variante': v.nombre_corto, 'sku': v.sku, 'stock': v.stock,
        'movimientos': [{
            'fecha': timezone.localtime(m.creado).strftime('%d/%m/%Y %H:%M'),
            'tipo': m.get_tipo_display(), 'entrada': m.es_entrada, 'cantidad': m.cantidad,
            'motivo': m.motivo, 'referencia': m.referencia,
            'stock': f'{m.stock_anterior} → {m.stock_nuevo}',
            'usuario': (m.usuario.get_full_name() or m.usuario.email) if m.usuario else 'Sistema',
        } for m in movs],
    })


# --- Pedidos ---------------------------------------------------------------------

def _rango_fechas(desde, hasta):
    tz = timezone.get_current_timezone()
    ini = timezone.make_aware(datetime.combine(desde, time.min), tz) if desde else None
    fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min), tz) if hasta else None
    return ini, fin


@staff_requerido
def pedidos(request):
    filtros = FiltroPedidosForm(request.GET or None)
    qs = Pedido.objects.select_related('usuario', 'sucursal').order_by('-creado')
    if filtros.is_valid():
        cd = filtros.cleaned_data
        if cd['estado']:
            qs = qs.filter(estado=cd['estado'])
        if cd['entrega']:
            qs = qs.filter(metodo_entrega=cd['entrega'])
        ini, fin = _rango_fechas(cd['desde'], cd['hasta'])
        if ini:
            qs = qs.filter(creado__gte=ini)
        if fin:
            qs = qs.filter(creado__lt=fin)
    pagina = _paginar(request, qs)

    sel = None
    codigo = request.GET.get('pedido')
    if codigo:
        sel = (Pedido.objects.select_related('usuario__perfil', 'sucursal', 'actualizado_por')
               .prefetch_related('items__variante', 'items__producto', 'eventos__usuario')
               .filter(codigo=codigo).first())
    elif pagina.object_list:
        sel = (Pedido.objects.select_related('usuario__perfil', 'sucursal', 'actualizado_por')
               .prefetch_related('items__variante', 'items__producto', 'eventos__usuario')
               .get(pk=pagina.object_list[0].pk))

    return render(request, 'panel/pedidos.html', {
        'seccion': 'pedidos', 'filtros': filtros, 'pedidos': pagina, 'sel': sel,
        'despacho_form': DespachoForm(prefix='des'),
    })


@staff_requerido
@require_POST
def pedido_estado(request, codigo):
    pedido = get_object_or_404(Pedido, codigo=codigo)
    destino = f"{request.POST.get('volver') or reverse('panel:pedidos')}"
    nuevo = request.POST.get('estado')
    permitidos = dict(pedido.estados_permitidos())
    if nuevo == pedido.estado:
        messages.info(request, 'El pedido ya está en ese estado.')
    elif nuevo not in permitidos:
        messages.error(request, 'Ese cambio de estado no está permitido para este pedido.')
    else:
        cambiar_estado(pedido, nuevo, request.user)
        messages.success(request, f'Pedido {pedido.codigo}: {pedido.get_estado_display()}.')
    return redirect(destino)


@staff_requerido
@require_POST
def pedido_despacho(request, codigo):
    pedido = get_object_or_404(Pedido, codigo=codigo)
    destino = request.POST.get('volver') or reverse('panel:pedidos')
    if not pedido.requiere_despacho:
        messages.error(request, 'Solo se registra despacho en pedidos a domicilio que están en preparación.')
        return redirect(destino)
    form = DespachoForm(request.POST, prefix='des')
    if not form.is_valid():
        errores = ' '.join(e for errs in form.errors.values() for e in errs)
        messages.error(request, f'No se pudo registrar el despacho. {errores}')
        return redirect(destino)
    cambiar_estado(pedido, Pedido.Estado.ENVIADO, request.user, despacho=form.cleaned_data)
    messages.success(request, f'Despacho registrado. Pedido {pedido.codigo} enviado con guía {pedido.numero_guia}.')
    return redirect(destino)


# --- Reportes ----------------------------------------------------------------------

def _datos_reporte(cd):
    hoy = timezone.localdate()
    desde = cd.get('desde') or hoy.replace(day=1)
    hasta = cd.get('hasta') or hoy
    ini, fin = _rango_fechas(desde, hasta)
    pedidos_qs = (Pedido.objects.filter(estado__in=Pedido.CONFIRMADOS, pagado_en__gte=ini, pagado_en__lt=fin)
                  .prefetch_related('items__producto__deporte'))
    if cd.get('entrega'):
        pedidos_qs = pedidos_qs.filter(metodo_entrega=cd['entrega'])
    filtro_dep = cd.get('categoria')

    filas = defaultdict(lambda: {'pedidos': 0, 'unidades': 0, 'domicilio': 0, 'retiro': 0, 'total': Decimal('0')})
    n_pedidos = unidades = 0
    total = Decimal('0')
    for p in pedidos_qs:
        items = [i for i in p.items.all() if not filtro_dep or i.producto.deporte_id == filtro_dep.pk]
        if not items:
            continue
        por_dep = defaultdict(Decimal)
        for i in items:
            dep = i.producto.deporte.nombre
            por_dep[dep] += i.subtotal()
            filas[dep]['unidades'] += i.cantidad
            filas[dep]['total'] += i.subtotal()
            unidades += i.cantidad
            total += i.subtotal()
        # Cada pedido se cuenta una sola vez, en su categoria principal (la de mayor importe)
        principal = max(por_dep, key=por_dep.get)
        filas[principal]['pedidos'] += 1
        filas[principal]['domicilio' if p.es_domicilio else 'retiro'] += 1
        n_pedidos += 1

    filas = sorted(({'categoria': k, **v} for k, v in filas.items()), key=lambda f: f['total'], reverse=True)
    totales = {k: sum(f[k] for f in filas) for k in ('pedidos', 'unidades', 'domicilio', 'retiro', 'total')}
    return {'desde': desde, 'hasta': hasta, 'pedidos': n_pedidos, 'unidades': unidades, 'total': total,
            'filas': filas, 'totales': totales}


@staff_requerido
def reportes(request):
    filtros = FiltroReporteForm(request.GET or None)
    cd = filtros.cleaned_data if filtros.is_valid() else {}
    datos = _datos_reporte(cd)
    if not request.GET:
        # Sin filtros: mostrar en los campos el periodo usado (mes en curso)
        filtros = FiltroReporteForm(initial={'desde': datos['desde'].isoformat(), 'hasta': datos['hasta'].isoformat()})

    if request.GET.get('exportar') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="ventas_{datos["desde"]:%Y%m%d}_{datos["hasta"]:%Y%m%d}.csv"'
        resp.write('﻿')  # BOM para que Excel lea los acentos
        w = csv.writer(resp)
        w.writerow(['Categoría', 'Pedidos', 'Unidades', 'Domicilio', 'Retiro', 'Total (USD)'])
        for f in datos['filas']:
            w.writerow([f['categoria'], f['pedidos'], f['unidades'], f['domicilio'], f['retiro'], f'{f["total"]:.2f}'])
        t = datos['totales']
        w.writerow(['Total', t['pedidos'], t['unidades'], t['domicilio'], t['retiro'], f'{t["total"]:.2f}'])
        return resp

    return render(request, 'panel/reportes.html', {
        'seccion': 'reportes', 'filtros': filtros, 'd': datos, 'ahora': timezone.localtime(),
    })
