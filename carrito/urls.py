from django.urls import path

from . import views

app_name = 'carrito'

urlpatterns = [
    path('', views.detalle, name='detalle'),
    path('agregar/<int:variante_id>/', views.agregar, name='agregar'),
    path('eliminar/<int:variante_id>/', views.eliminar, name='eliminar'),
    path('vaciar/', views.vaciar, name='vaciar'),
]
