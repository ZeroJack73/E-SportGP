from django.contrib import admin

from .models import (Categoria, Color, Deporte, Marca, MovimientoInventario, Opinion, Producto,
                     ProductoImagen, Talla, Variante)


@admin.register(Deporte)
class DeporteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'slug', 'icono', 'orden']
    list_editable = ['orden']
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'slug', 'icono']
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'slug']
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Talla)
class TallaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'grupo', 'orden']
    list_filter = ['grupo']
    list_editable = ['orden']


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'hex', 'orden']
    list_editable = ['hex', 'orden']


class VarianteInline(admin.TabularInline):
    model = Variante
    extra = 1


class ImagenInline(admin.TabularInline):
    model = ProductoImagen
    extra = 1


class OpinionInline(admin.StackedInline):
    model = Opinion
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'deporte', 'categoria', 'marca', 'precio', 'stock_total',
                    'disponible', 'destacado', 'es_nuevo']
    list_filter = ['disponible', 'destacado', 'es_nuevo', 'deporte', 'categoria', 'marca']
    list_editable = ['precio', 'disponible', 'destacado', 'es_nuevo']
    search_fields = ['nombre', 'descripcion']
    prepopulated_fields = {'slug': ('nombre',)}
    inlines = [VarianteInline, ImagenInline, OpinionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).con_stock()

    @admin.display(description='Stock', ordering='stock_total')
    def stock_total(self, obj):
        return obj.stock_total


@admin.register(Opinion)
class OpinionAdmin(admin.ModelAdmin):
    list_display = ['producto', 'nombre', 'calificacion', 'verificada', 'creado']
    list_filter = ['calificacion', 'verificada']


@admin.register(MovimientoInventario)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ['creado', 'variante', 'tipo', 'cantidad', 'stock_anterior', 'stock_nuevo', 'motivo', 'usuario']
    list_filter = ['tipo', 'creado']
    search_fields = ['variante__sku', 'variante__producto__nombre', 'referencia']

    def has_change_permission(self, request, obj=None):
        return False  # el historial no se edita
