from django.urls import path

from . import views

app_name = 'cuentas'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('registro/', views.registro, name='registro'),
    path('perfil/', views.perfil, name='perfil'),
    path('direcciones/', views.direcciones, name='direcciones'),
    path('direcciones/nueva/', views.direcciones, {'nueva': True}, name='direccion_nueva'),
    path('direcciones/<int:pk>/editar/', views.direcciones, name='direccion_editar'),
    path('direcciones/<int:pk>/eliminar/', views.eliminar_direccion, name='direccion_eliminar'),
    path('direcciones/<int:pk>/predeterminar/', views.predeterminar_direccion, name='direccion_predeterminar'),
    path('recuperar/', views.PasswordResetView.as_view(), name='password_reset'),
    path('recuperar/enviado/', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('recuperar/<uidb64>/<token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
