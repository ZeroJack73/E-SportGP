from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Direccion, Perfil


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False


admin.site.unregister(User)


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    inlines = [PerfilInline]


@admin.register(Direccion)
class DireccionAdmin(admin.ModelAdmin):
    list_display = ['alias', 'usuario', 'recibe', 'distrito', 'provincia', 'predeterminada']
    list_filter = ['provincia', 'predeterminada']
    search_fields = ['alias', 'recibe', 'usuario__email']
