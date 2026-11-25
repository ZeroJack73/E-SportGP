from django.urls import path

from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('productos/', views.productos, name='productos'),
    path('productos/nuevo/', views.producto_form, name='producto_nuevo'),
    path('productos/<int:pk>/', views.producto_form, name='producto_editar'),
    path('productos/<int:pk>/estado/', views.producto_estado, name='producto_estado'),
    path('categorias/', views.categorias, name='categorias'),
    path('categorias/guardar/', views.categoria_guardar, name='categoria_guardar'),
    path('categorias/<str:tipo>/<int:pk>/eliminar/', views.categoria_eliminar, name='categoria_eliminar'),
    path('inventario/', views.inventario, name='inventario'),
    path('inventario/<int:pk>/historial/', views.historial_variante, name='historial'),
    path('pedidos/', views.pedidos, name='pedidos'),
    path('pedidos/<str:codigo>/estado/', views.pedido_estado, name='pedido_estado'),
    path('pedidos/<str:codigo>/despacho/', views.pedido_despacho, name='pedido_despacho'),
    path('reportes/', views.reportes, name='reportes'),
]
