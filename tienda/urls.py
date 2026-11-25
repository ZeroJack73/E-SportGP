from django.urls import path

from . import views

app_name = 'tienda'

urlpatterns = [
    path('', views.catalogo, name='inicio'),
    path('productos/', views.catalogo, name='lista'),
    path('producto/<slug:slug>/', views.detalle_producto, name='detalle'),
    path('salud/', views.salud, name='salud'),
]
