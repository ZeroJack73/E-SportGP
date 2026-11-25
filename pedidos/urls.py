from django.urls import path

from . import views

app_name = 'pedidos'

urlpatterns = [
    path('', views.mis_pedidos, name='lista'),
    path('checkout/', views.checkout, name='checkout'),
    path('<str:codigo>/pago/', views.pasarela, name='pasarela'),
    path('<str:codigo>/confirmacion/', views.confirmacion, name='confirmacion'),
    path('<str:codigo>/cancelar/', views.cancelar, name='cancelar'),
    path('<str:codigo>/calificar/', views.calificar, name='calificar'),
]
