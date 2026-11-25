from django.conf import settings

from .models import Deporte


def categorias(request):
    return {
        'deportes_menu': Deporte.objects.all(),
        'envio_gratis_desde': settings.ENVIO_GRATIS_DESDE,
    }
