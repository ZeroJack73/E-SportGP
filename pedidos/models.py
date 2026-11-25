from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from tienda.models import Producto, Variante


def sumar_dias_habiles(fecha, dias):
    while dias > 0:
        fecha += timedelta(days=1)
        if fecha.weekday() < 5:
            dias -= 1
    return fecha


class Sucursal(models.Model):
    nombre = models.CharField(max_length=80)
    direccion = models.CharField(max_length=200)
    horario = models.CharField(max_length=120, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'sucursales'

    def __str__(self):
        return self.nombre


class Pedido(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE_PAGO = 'pendiente_pago', 'Pendiente de pago'
        PAGADO = 'pagado', 'Pagado'
        EN_PREPARACION = 'en_preparacion', 'En preparación'
        ENVIADO = 'enviado', 'Enviado'
        LISTO_RETIRO = 'listo_retiro', 'Listo para retirar'
        ENTREGADO = 'entregado', 'Entregado'
        CANCELADO = 'cancelado', 'Cancelado'

    class Entrega(models.TextChoices):
        DOMICILIO = 'domicilio', 'Envío a domicilio'
        SUCURSAL = 'sucursal', 'Retiro en sucursal'

    CANCELABLES = {Estado.PENDIENTE_PAGO, Estado.PAGADO, Estado.EN_PREPARACION}
    # Estados que cuentan como venta confirmada (reportes)
    CONFIRMADOS = {Estado.PAGADO, Estado.EN_PREPARACION, Estado.ENVIADO, Estado.LISTO_RETIRO, Estado.ENTREGADO}

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='pedidos', on_delete=models.CASCADE)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE_PAGO)
    email = models.EmailField()

    # Entrega (copia de los datos al momento de la compra)
    metodo_entrega = models.CharField(max_length=10, choices=Entrega.choices, default=Entrega.DOMICILIO)
    direccion_alias = models.CharField(max_length=40, blank=True)
    recibe = models.CharField(max_length=120, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion_texto = models.TextField(blank=True)
    sucursal = models.ForeignKey(Sucursal, null=True, blank=True, on_delete=models.PROTECT)

    # Importes
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    envio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Pago
    referencia_pago = models.CharField(max_length=40, blank=True)
    pagado_en = models.DateTimeField(null=True, blank=True)
    entrega_desde = models.DateField(null=True, blank=True)
    entrega_hasta = models.DateField(null=True, blank=True)

    # Despacho (solo envio a domicilio)
    peso_kg = models.DecimalField('peso total (kg)', max_digits=7, decimal_places=2, null=True, blank=True)
    bultos = models.PositiveSmallIntegerField(null=True, blank=True)
    numero_guia = models.CharField('número de guía', max_length=40, blank=True)
    despachado_en = models.DateTimeField(null=True, blank=True)
    entregado_en = models.DateTimeField(null=True, blank=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='+',
                                        on_delete=models.SET_NULL)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return self.codigo or f'Pedido {self.pk}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = f'SP-{self.creado.year}-{self.pk:05d}'
            Pedido.objects.filter(pk=self.pk).update(codigo=self.codigo)

    # --- Reglas de negocio --------------------------------------------
    @property
    def puede_cancelarse(self):
        return self.estado in self.CANCELABLES

    @property
    def requiere_reembolso(self):
        return self.estado in {self.Estado.PAGADO, self.Estado.EN_PREPARACION}

    @property
    def es_domicilio(self):
        return self.metodo_entrega == self.Entrega.DOMICILIO

    @property
    def unidades(self):
        return sum(i.cantidad for i in self.items.all())

    @property
    def clase_estado(self):
        return {
            'pendiente_pago': 'estado--alerta',
            'en_preparacion': 'estado--alerta',
            'cancelado': 'estado--neutro',
        }.get(self.estado, 'estado--info')

    # --- Flujo de preparacion y entrega -------------------------------
    def siguiente_estado(self):
        """Pagado -> En preparacion -> Enviado (domicilio) / Listo para retirar (sucursal) -> Entregado."""
        E = self.Estado
        if self.estado == E.PAGADO:
            return E.EN_PREPARACION
        if self.estado == E.EN_PREPARACION:
            return E.ENVIADO if self.es_domicilio else E.LISTO_RETIRO
        if self.estado in (E.ENVIADO, E.LISTO_RETIRO):
            return E.ENTREGADO
        return None

    @property
    def siguiente_estado_display(self):
        sig = self.siguiente_estado()
        return self.Estado(sig).label if sig else ''

    @property
    def requiere_despacho(self):
        """El paso a Enviado exige registrar peso, bultos y guia."""
        return self.siguiente_estado() == self.Estado.ENVIADO

    def estados_permitidos(self):
        """Opciones validas para el selector del panel (estado actual + siguiente + cancelar)."""
        opciones = [self.estado]
        sig = self.siguiente_estado()
        if sig and not self.requiere_despacho:
            opciones.append(sig)
        if self.puede_cancelarse:
            opciones.append(self.Estado.CANCELADO)
        return [(e, self.Estado(e).label) for e in opciones]

    def marcar_pagado(self, referencia):
        ahora = timezone.now()
        self.estado = self.Estado.PAGADO
        self.referencia_pago = referencia
        self.pagado_en = ahora
        hoy = timezone.localdate(ahora)
        if self.es_domicilio:
            self.entrega_desde, self.entrega_hasta = sumar_dias_habiles(hoy, 3), sumar_dias_habiles(hoy, 5)
        else:
            self.entrega_desde, self.entrega_hasta = hoy + timedelta(days=1), hoy + timedelta(days=2)
        self.save()

    @staticmethod
    def calcular_envio(subtotal, metodo):
        if metodo == Pedido.Entrega.SUCURSAL or subtotal >= Decimal(settings.ENVIO_GRATIS_DESDE):
            return Decimal('0.00')
        return Decimal(settings.COSTO_ENVIO)


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='items', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, related_name='items_pedido', on_delete=models.PROTECT)
    variante = models.ForeignKey(Variante, null=True, blank=True, related_name='items_pedido',
                                 on_delete=models.SET_NULL)
    detalle_variante = models.CharField(max_length=120, blank=True,
                                        help_text='Copia de la talla y color al momento de la compra')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.cantidad} x {self.producto}'

    def subtotal(self):
        return self.precio * self.cantidad


class EventoPedido(models.Model):
    """Historial de cambios de estado de un pedido."""
    pedido = models.ForeignKey(Pedido, related_name='eventos', on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, choices=Pedido.Estado.choices)
    nota = models.CharField(max_length=200, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'evento de pedido'
        verbose_name_plural = 'eventos de pedido'

    def __str__(self):
        return f'{self.pedido} - {self.get_estado_display()}'
