from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.text import slugify


class SlugMixin(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)


class Deporte(SlugMixin):
    icono = models.CharField(max_length=50, default='bi-trophy',
                             help_text='Clase de Bootstrap Icons, por ejemplo: bi-bicycle')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta(SlugMixin.Meta):
        ordering = ['orden', 'nombre']

    def get_absolute_url(self):
        return f"{reverse('tienda:inicio')}?deporte={self.slug}"


class Categoria(SlugMixin):
    icono = models.CharField(max_length=50, default='bi-tag',
                             help_text='Clase de Bootstrap Icons, por ejemplo: bi-bag')

    class Meta(SlugMixin.Meta):
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'

    def get_absolute_url(self):
        return f"{reverse('tienda:inicio')}?categoria={self.slug}"


class Marca(SlugMixin):
    pass


class Talla(models.Model):
    class Grupo(models.TextChoices):
        ROPA = 'ropa', 'Ropa (letras)'
        CALZADO = 'calzado', 'Calzado (MX / cm)'

    nombre = models.CharField(max_length=10, unique=True)
    grupo = models.CharField(max_length=10, choices=Grupo.choices, default=Grupo.ROPA)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-grupo', 'orden']  # primero ropa, luego calzado

    def __str__(self):
        return self.nombre


class Color(models.Model):
    nombre = models.CharField(max_length=30, unique=True)
    hex = models.CharField(max_length=7, help_text='Ejemplo: #1F5BD8')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden']
        verbose_name_plural = 'colores'

    def __str__(self):
        return self.nombre


class ProductoQuerySet(models.QuerySet):
    def con_stock(self):
        """Anota stock_total sin multiplicar filas al combinarse con otros filtros."""
        total = (Variante.objects.filter(producto=OuterRef('pk'))
                 .values('producto').annotate(t=Sum('stock')).values('t'))
        return self.annotate(stock_total=Coalesce(Subquery(total), 0))


class Producto(models.Model):
    POCAS_UNIDADES = 5

    deporte = models.ForeignKey(Deporte, related_name='productos', on_delete=models.PROTECT)
    categoria = models.ForeignKey(Categoria, related_name='productos', on_delete=models.PROTECT)
    marca = models.ForeignKey(Marca, related_name='productos', on_delete=models.PROTECT)
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    descripcion = models.TextField(blank=True)
    material = models.CharField(max_length=250, blank=True,
                                help_text='Ejemplo: Upper de malla transpirable · Entresuela EVA')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField('imagen principal', upload_to='productos/', blank=True)
    etiqueta_imagen = models.CharField('vista de la imagen principal', max_length=40, default='Vista lateral')
    disponible = models.BooleanField(default=True, help_text='Visible en la tienda')
    destacado = models.BooleanField(default=False)
    es_nuevo = models.BooleanField('nuevo', default=False)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = ProductoQuerySet.as_manager()

    class Meta:
        ordering = ['-destacado', '-creado']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre)
            slug, n = base, 1
            while Producto.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f'{base}-{n}'
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('tienda:detalle', args=[self.slug])

    # --- Stock ---------------------------------------------------------
    @property
    def stock(self):
        if hasattr(self, 'stock_total'):
            return self.stock_total
        return self.variantes.aggregate(t=Sum('stock'))['t'] or 0

    @property
    def en_stock(self):
        return self.disponible and self.stock > 0

    @property
    def pocas_unidades(self):
        return 0 < self.stock <= self.POCAS_UNIDADES

    # --- Opiniones -----------------------------------------------------
    def resumen_opiniones(self):
        r = self.opiniones.aggregate(promedio=Avg('calificacion'), total=Count('id'))
        r['promedio'] = round(r['promedio'], 1) if r['promedio'] else None
        return r

    # --- Galeria -------------------------------------------------------
    def galeria(self):
        fotos = []
        if self.imagen:
            fotos.append({'url': self.imagen.url, 'etiqueta': self.etiqueta_imagen})
        fotos += [{'url': i.imagen.url, 'etiqueta': i.etiqueta} for i in self.imagenes.all()]
        return fotos


PALABRAS_VACIAS = {'de', 'del', 'la', 'el', 'para', 'con', 'y', 'ml', 'kg'}


class Variante(models.Model):
    """Combinacion de talla y color con su propio stock."""
    producto = models.ForeignKey(Producto, related_name='variantes', on_delete=models.CASCADE)
    talla = models.ForeignKey(Talla, null=True, blank=True, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, null=True, blank=True, on_delete=models.PROTECT)
    sku = models.CharField('SKU', max_length=40, unique=True, blank=True,
                           help_text='Se genera automáticamente si se deja vacío')
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField('stock mínimo', default=5)

    class Meta:
        ordering = ['talla__orden', 'color__orden']
        constraints = [models.UniqueConstraint(fields=['producto', 'talla', 'color'], name='variante_unica')]

    def __str__(self):
        return f'{self.producto} ({self.descripcion or "única"})'

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self.generar_sku()
        super().save(*args, **kwargs)

    def generar_sku(self):
        """Ej.: SP-VP-LI-27 (marca - producto - color - talla)."""
        marca = slugify(self.producto.marca.nombre).replace('-', '')[:2].upper()
        palabras = [p for p in slugify(self.producto.nombre).split('-') if p not in PALABRAS_VACIAS]
        modelo = ''.join(p[0] for p in palabras[-2:]).upper()
        partes = [marca, modelo]
        if self.color:
            partes.append(slugify(self.color.nombre)[:2].upper())
        if self.talla:
            partes.append(self.talla.nombre.upper())
        base = '-'.join(partes)
        sku, n = base, 1
        while Variante.objects.filter(sku=sku).exclude(pk=self.pk).exists():
            n += 1
            sku = f'{base}-{n}'
        return sku

    @property
    def alerta(self):
        if self.stock == 0:
            return 'agotado'
        if self.stock <= self.stock_minimo:
            return 'bajo'
        return 'normal'

    @property
    def nombre_corto(self):
        """Ej.: Velocity Pro · 27 · Lima (para tablas del panel)."""
        partes = [self.producto.nombre]
        if self.talla:
            partes.append(self.talla.nombre)
        if self.color:
            partes.append(self.color.nombre)
        return ' · '.join(partes)

    def clean(self):
        # La restriccion de la base no detecta duplicados con talla o color vacios (NULL)
        duplicada = Variante.objects.filter(producto_id=self.producto_id, talla=self.talla,
                                            color=self.color).exclude(pk=self.pk)
        if self.producto_id and duplicada.exists():
            raise ValidationError('Ya existe una variante con esta talla y color.')

    @property
    def descripcion(self):
        """Ej.: Talla 27 cm · Negro"""
        partes = []
        if self.talla:
            sufijo = ' cm' if self.talla.grupo == Talla.Grupo.CALZADO else ''
            partes.append(f'Talla {self.talla.nombre}{sufijo}')
        if self.color:
            partes.append(self.color.nombre)
        return ' · '.join(partes)

    @property
    def descripcion_corta(self):
        """Ej.: 27 cm · Negro"""
        partes = []
        if self.talla:
            partes.append(f'{self.talla.nombre} cm' if self.talla.grupo == Talla.Grupo.CALZADO else self.talla.nombre)
        if self.color:
            partes.append(self.color.nombre)
        return ' · '.join(partes)


class ProductoImagen(models.Model):
    producto = models.ForeignKey(Producto, related_name='imagenes', on_delete=models.CASCADE)
    imagen = models.ImageField(upload_to='productos/galeria/')
    etiqueta = models.CharField(max_length=40, help_text='Ejemplo: Vista trasera, Detalle')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden']
        verbose_name = 'imagen adicional'
        verbose_name_plural = 'imagenes adicionales'

    def __str__(self):
        return f'{self.producto} - {self.etiqueta}'


class Opinion(models.Model):
    producto = models.ForeignKey(Producto, related_name='opiniones', on_delete=models.CASCADE)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    nombre = models.CharField(max_length=60, help_text='Nombre visible, ejemplo: Andrea M.')
    calificacion = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.TextField()
    verificada = models.BooleanField('compra verificada', default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']
        verbose_name_plural = 'opiniones'

    def __str__(self):
        return f'{self.nombre}: {self.calificacion}/5'


class StockNegativo(Exception):
    """Un movimiento dejaria el stock por debajo de cero."""


class MovimientoInventario(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = 'entrada', 'Entrada'
        SALIDA = 'salida', 'Salida'
        VENTA = 'venta', 'Venta'
        DEVOLUCION = 'devolucion', 'Devolución por cancelación'

    MOTIVOS = [
        'Reposición de proveedor', 'Devolución de cliente', 'Corrección de inventario',
        'Producto dañado o merma', 'Venta en tienda física', 'Muestra o promoción',
    ]

    variante = models.ForeignKey(Variante, related_name='movimientos', on_delete=models.CASCADE)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    cantidad = models.PositiveIntegerField()
    motivo = models.CharField(max_length=120)
    stock_anterior = models.PositiveIntegerField()
    stock_nuevo = models.PositiveIntegerField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    referencia = models.CharField(max_length=40, blank=True, help_text='Ej.: código de pedido')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'movimiento de inventario'
        verbose_name_plural = 'movimientos de inventario'

    def __str__(self):
        return f'{self.get_tipo_display()} {self.cantidad} - {self.variante.sku}'

    @property
    def es_entrada(self):
        return self.tipo in (self.Tipo.ENTRADA, self.Tipo.DEVOLUCION)

    @classmethod
    def registrar(cls, variante_id, tipo, cantidad, motivo, usuario=None, referencia=''):
        """Aplica el movimiento con bloqueo de fila y lo deja registrado.
        Debe llamarse dentro de transaction.atomic(). Lanza StockNegativo si no alcanza."""
        variante = Variante.objects.select_for_update().get(pk=variante_id)
        entrada = tipo in (cls.Tipo.ENTRADA, cls.Tipo.DEVOLUCION)
        nuevo = variante.stock + cantidad if entrada else variante.stock - cantidad
        if nuevo < 0:
            raise StockNegativo(variante)
        anterior = variante.stock
        variante.stock = nuevo
        variante.save(update_fields=['stock'])
        return cls.objects.create(variante=variante, tipo=tipo, cantidad=cantidad, motivo=motivo,
                                  stock_anterior=anterior, stock_nuevo=nuevo,
                                  usuario=usuario, referencia=referencia)
