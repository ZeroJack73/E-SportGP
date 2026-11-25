from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Permite iniciar sesion con el correo electronico."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        usuario = User.objects.filter(email__iexact=username).order_by('id').first()
        if usuario is None:
            User().set_password(password)  # tiempo constante ante usuarios inexistentes
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
