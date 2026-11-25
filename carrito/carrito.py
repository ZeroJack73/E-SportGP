from decimal import Decimal

from django.conf import settings

from tienda.models import Variante


class Carrito:
    """Carrito de compras guardado en la sesion. Cada linea es una variante (talla + color)."""

    def __init__(self, request):
        self.session = request.session
        carrito = self.session.get(settings.CARRITO_SESSION_ID)
        if carrito is None:
            carrito = self.session[settings.CARRITO_SESSION_ID] = {}
        self.carrito = carrito

    def cantidad_de(self, variante):
        return self.carrito.get(str(variante.id), {}).get('cantidad', 0)

    def agregar(self, variante, cantidad=1, reemplazar=False):
        vid = str(variante.id)
        if vid not in self.carrito:
            self.carrito[vid] = {'cantidad': 0, 'precio': str(variante.producto.precio)}
        nueva = cantidad if reemplazar else self.carrito[vid]['cantidad'] + cantidad
        # Nunca superar el stock de la variante
        self.carrito[vid]['cantidad'] = max(0, min(nueva, variante.stock))
        if self.carrito[vid]['cantidad'] == 0:
            del self.carrito[vid]
        self.guardar()

    def eliminar(self, variante):
        vid = str(variante.id)
        if vid in self.carrito:
            del self.carrito[vid]
            self.guardar()

    def limpiar(self):
        self.session[settings.CARRITO_SESSION_ID] = {}
        self.session.modified = True

    def guardar(self):
        self.session.modified = True

    def __iter__(self):
        variantes = (Variante.objects.filter(id__in=self.carrito.keys())
                     .select_related('producto__deporte', 'producto__marca', 'talla', 'color'))
        por_id = {str(v.id): v for v in variantes}
        for vid, datos in self.carrito.items():
            variante = por_id.get(vid)
            if variante is None:
                continue
            precio = Decimal(datos['precio'])
            yield {
                'variante': variante,
                'producto': variante.producto,
                'cantidad': datos['cantidad'],
                'precio': precio,
                'subtotal': precio * datos['cantidad'],
            }

    def __len__(self):
        return sum(item['cantidad'] for item in self.carrito.values())

    @property
    def lineas(self):
        """Cantidad de productos distintos (lineas) en el carrito."""
        return len(self.carrito)

    def total(self):
        return sum(Decimal(i['precio']) * i['cantidad'] for i in self.carrito.values())
