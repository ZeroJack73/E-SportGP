from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import BootstrapMixin, DireccionForm, LoginForm, PerfilForm, RegistroForm
from .models import Direccion


class LoginView(auth_views.LoginView):
    template_name = 'cuentas/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        usuario = form.get_user()
        if usuario.is_staff:
            messages.success(self.request, 'Sesión de administración iniciada.')
        else:
            messages.success(self.request, f'Qué bueno verte de nuevo, {usuario.first_name or usuario.email}.')
        return super().form_valid(form)

    def get_default_redirect_url(self):
        # Acceso por rol: los administradores van al panel, los clientes a la tienda
        if self.request.user.is_staff:
            return reverse('panel:inicio')
        return super().get_default_redirect_url()


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, 'Sesión cerrada correctamente.')
        return response


def registro(request):
    if request.user.is_authenticated:
        return redirect('tienda:inicio')
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario, backend='cuentas.backends.EmailBackend')
            messages.success(request, 'Tu cuenta se creó con éxito. Bienvenido a SportPG.')
            return redirect(request.GET.get('next') or 'tienda:inicio')
    else:
        form = RegistroForm()
    return render(request, 'cuentas/registro.html', {'form': form})


@login_required
def perfil(request):
    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado.')
            return redirect('cuentas:perfil')
    else:
        form = PerfilForm(instance=request.user)
    return render(request, 'cuentas/perfil.html', {'form': form})


# Recuperacion de contrasena (vistas de Django con el diseno de SportPG)

class PasswordResetForm(BootstrapMixin, auth_forms.PasswordResetForm):
    pass


class SetPasswordForm(BootstrapMixin, auth_forms.SetPasswordForm):
    pass


class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'cuentas/password_reset.html'
    email_template_name = 'cuentas/email/password_reset.txt'
    subject_template_name = 'cuentas/email/password_reset_asunto.txt'
    form_class = PasswordResetForm
    success_url = reverse_lazy('cuentas:password_reset_done')


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'cuentas/password_reset_done.html'


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'cuentas/password_reset_confirm.html'
    form_class = SetPasswordForm
    success_url = reverse_lazy('cuentas:login')

    def form_valid(self, form):
        messages.success(self.request, 'Tu contraseña se actualizó. Ya puedes iniciar sesión.')
        return super().form_valid(form)


# --- Mis direcciones ----------------------------------------------------

def _destino_seguro(request, por_defecto='cuentas:direcciones'):
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return reverse(por_defecto)


@login_required
def direcciones(request, pk=None, nueva=False):
    """Lista de direcciones; con nueva=True o pk muestra el formulario de alta/edicion."""
    lista = request.user.direcciones.all()
    instancia = get_object_or_404(Direccion, pk=pk, usuario=request.user) if pk else None
    mostrar_form = nueva or instancia is not None
    form = None

    if mostrar_form:
        if request.method == 'POST':
            form = DireccionForm(request.POST, instance=instancia)
            if form.is_valid():
                direccion = form.save(commit=False)
                direccion.usuario = request.user
                direccion.save()
                messages.success(request, 'Dirección actualizada.' if instancia else 'Dirección agregada.')
                return redirect(_destino_seguro(request))
        else:
            inicial = {}
            if not instancia:
                u = request.user
                inicial = {'recibe': u.get_full_name(),
                           'telefono': getattr(getattr(u, 'perfil', None), 'telefono', ''),
                           'alias': 'Casa' if not lista else ''}
            form = DireccionForm(instance=instancia, initial=inicial)

    return render(request, 'cuentas/direcciones.html', {
        'direcciones': lista,
        'form': form,
        'editando': instancia,
        'next': _next_seguro(request),
    })


def _next_seguro(request):
    destino = request.POST.get('next') or request.GET.get('next') or ''
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return ''


@login_required
@require_POST
def eliminar_direccion(request, pk):
    direccion = get_object_or_404(Direccion, pk=pk, usuario=request.user)
    alias = direccion.alias
    direccion.delete()
    messages.success(request, f'Se eliminó la dirección "{alias}".')
    return redirect('cuentas:direcciones')


@login_required
@require_POST
def predeterminar_direccion(request, pk):
    direccion = get_object_or_404(Direccion, pk=pk, usuario=request.user)
    direccion.predeterminada = True
    direccion.save()
    messages.success(request, f'"{direccion.alias}" es ahora tu dirección predeterminada.')
    return redirect('cuentas:direcciones')
