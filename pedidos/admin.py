from django.contrib import admin

from .models import EventoPedido, ItemPedido, Pedido, Sucursal


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    raw_id_fields = ['producto', 'variante']
    extra = 0


class EventoInline(admin.TabularInline):
    model = EventoPedido
    extra = 0
    readonly_fields = ['estado', 'nota', 'usuario', 'creado']
    can_delete = False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'usuario', 'metodo_entrega', 'total', 'estado', 'creado']
    list_filter = ['estado', 'metodo_entrega', 'creado']
    list_editable = ['estado']
    search_fields = ['codigo', 'usuario__email', 'recibe']
    readonly_fields = ['codigo', 'referencia_pago', 'pagado_en', 'creado']
    inlines = [ItemPedidoInline, EventoInline]


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'direccion', 'activa']
    list_editable = ['activa']
