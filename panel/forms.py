from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from pedidos.models import Pedido
from tienda.models import Categoria, Deporte, MovimientoInventario, Producto, Variante

MAX_IMAGEN = settings.MAX_IMAGEN_MB * 1024 * 1024
TIPOS_IMAGEN = {'image/jpeg', 'image/png'}


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, forms.Select):
                w.attrs.setdefault('class', 'form-select')
            elif isinstance(w, forms.FileInput):
                w.attrs.setdefault('class', 'd-none')
            else:
                w.attrs.setdefault('class', 'form-control')


def validar_imagen(archivo):
    if not archivo:
        return archivo
    if archivo.size > MAX_IMAGEN:
        raise ValidationError(f'La imagen supera {settings.MAX_IMAGEN_MB} MB.')
    tipo = getattr(archivo, 'content_type', None)
    if tipo and tipo not in TIPOS_IMAGEN:
        raise ValidationError('Solo se aceptan imágenes JPG o PNG.')
    return archivo


# --- Productos -------------------------------------------------------------

class ProductoForm(BootstrapMixin, forms.ModelForm):
    deporte_categoria = forms.ChoiceField(label='Categoría')
    imagen_frontal = forms.ImageField(required=False, label='Frontal', validators=[validar_imagen])
    imagen_detalle = forms.ImageField(required=False, label='Detalle', validators=[validar_imagen])
    quitar_frontal = forms.BooleanField(required=False)
    quitar_detalle = forms.BooleanField(required=False)

    class Meta:
        model = Producto
        fields = ['nombre', 'marca', 'precio', 'descripcion', 'material', 'imagen',
                  'disponible', 'es_nuevo', 'destacado']
        labels = {'nombre': 'Nombre del producto', 'precio': 'Precio (USD)', 'imagen': 'Principal',
                  'descripcion': 'Descripción', 'disponible': 'Producto activo',
                  'es_nuevo': 'Marcar como nuevo', 'destacado': 'Destacado en el catálogo'}
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'precio': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'imagen': forms.FileInput(attrs={'accept': 'image/jpeg,image/png'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deporte_categoria'].choices = [('', 'Selecciona')] + [
            (f'{d.pk}-{c.pk}', f'{d.nombre} / {c.nombre}')
            for d in Deporte.objects.all() for c in Categoria.objects.all()]
        self.fields['deporte_categoria'].widget.attrs['class'] = 'form-select'
        self.fields['imagen'].validators.append(validar_imagen)
        for nombre in ('imagen_frontal', 'imagen_detalle'):
            self.fields[nombre].widget.attrs.update({'class': 'd-none', 'accept': 'image/jpeg,image/png'})
        if self.instance.pk:
            self.initial['deporte_categoria'] = f'{self.instance.deporte_id}-{self.instance.categoria_id}'
        self.fields['marca'].empty_label = 'Selecciona'

    def clean_deporte_categoria(self):
        valor = self.cleaned_data['deporte_categoria']
        try:
            dep, cat = (int(x) for x in valor.split('-'))
            return Deporte.objects.get(pk=dep), Categoria.objects.get(pk=cat)
        except (ValueError, Deporte.DoesNotExist, Categoria.DoesNotExist):
            raise ValidationError('Elige una categoría válida.')

    def save(self, commit=True):
        producto = super().save(commit=False)
        producto.deporte, producto.categoria = self.cleaned_data['deporte_categoria']
        if commit:
            producto.save()
        return producto


class VarianteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Variante
        fields = ['talla', 'color', 'sku', 'stock_minimo']
        labels = {'stock_minimo': 'Mínimo'}
        widgets = {'sku': forms.TextInput(attrs={'placeholder': 'Automático'}),
                   'stock_minimo': forms.NumberInput(attrs={'min': 0})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['talla'].empty_label = 'Única'
        self.fields['color'].empty_label = 'Único'
        for f in self.fields.values():
            f.widget.attrs['class'] += ' form-select-sm' if isinstance(f.widget, forms.Select) else ' form-control-sm'

    def clean_sku(self):
        # Vacio -> None: el formset no lo cuenta como duplicado y el modelo lo genera al guardar
        sku = (self.cleaned_data.get('sku') or '').strip().upper()
        return sku or None

    def has_changed(self):
        # Una fila nueva "Única / Único" sin cambios tambien es una variante valida
        return True if not self.instance.pk else super().has_changed()


class BaseVarianteFormSet(BaseInlineFormSet):
    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        form.empty_permitted = False  # las filas agregadas siempre se validan y guardan
        return form

    def clean(self):
        super().clean()
        vistos, activas = set(), 0
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or not form.cleaned_data:
                continue
            if form.cleaned_data.get('DELETE'):
                if form.instance.pk and form.instance.stock > 0:
                    raise ValidationError(
                        f'La variante {form.instance.sku} tiene {form.instance.stock} unidades en stock. '
                        'Registra una salida en Inventario antes de eliminarla.')
                continue
            clave = (form.cleaned_data.get('talla'), form.cleaned_data.get('color'))
            if clave in vistos:
                raise ValidationError('Hay variantes repetidas con la misma talla y color.')
            vistos.add(clave)
            activas += 1
        if activas == 0:
            raise ValidationError('Agrega al menos una variante (talla y color, o "Única").')


VarianteFormSet = inlineformset_factory(
    Producto, Variante, form=VarianteForm, formset=BaseVarianteFormSet,
    extra=0, can_delete=True)


# --- Categorias -------------------------------------------------------------

class NodoCategoriaForm(forms.Form):
    TIPOS = [('deporte', 'Deporte (categoría principal)'), ('categoria', 'Categoría de producto')]
    tipo = forms.ChoiceField(choices=TIPOS)
    nombre = forms.CharField(max_length=100)
    icono = forms.CharField(max_length=50, required=False)

    def clean_icono(self):
        icono = self.cleaned_data['icono'].strip() or 'bi-tag'
        if not icono.startswith('bi-'):
            icono = f'bi-{icono}'
        return icono


# --- Inventario -------------------------------------------------------------

class MovimientoForm(BootstrapMixin, forms.Form):
    TIPOS = [(MovimientoInventario.Tipo.ENTRADA, 'Entrada'), (MovimientoInventario.Tipo.SALIDA, 'Salida')]
    variante = forms.ModelChoiceField(
        queryset=Variante.objects.select_related('producto', 'talla', 'color').order_by('producto__nombre', 'talla__orden', 'color__orden'),
        empty_label='Selecciona una variante')
    tipo = forms.ChoiceField(choices=TIPOS, label='Tipo de movimiento')
    cantidad = forms.IntegerField(min_value=1, max_value=100000)
    motivo = forms.ChoiceField(choices=[(m, m) for m in MovimientoInventario.MOTIVOS])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['variante'].label_from_instance = lambda v: f'{v.nombre_corto} ({v.sku})'

    def clean(self):
        cd = super().clean()
        v, tipo, cant = cd.get('variante'), cd.get('tipo'), cd.get('cantidad')
        if v and cant and tipo == MovimientoInventario.Tipo.SALIDA and cant > v.stock:
            self.add_error('cantidad', f'La salida dejaría stock negativo: solo hay {v.stock} unidades.')
        return cd


# --- Pedidos ----------------------------------------------------------------

class DespachoForm(BootstrapMixin, forms.Form):
    peso_kg = forms.DecimalField(label='Peso total (kg)', min_value=0.01, max_digits=7, decimal_places=2)
    bultos = forms.IntegerField(min_value=1, max_value=999)
    numero_guia = forms.CharField(label='Número de guía', max_length=40)


class FiltroPedidosForm(BootstrapMixin, forms.Form):
    estado = forms.ChoiceField(required=False, choices=[('', 'Todos')] + list(Pedido.Estado.choices))
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    entrega = forms.ChoiceField(required=False, choices=[('', 'Todos')] + list(Pedido.Entrega.choices))


class FiltroReporteForm(BootstrapMixin, forms.Form):
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    categoria = forms.ModelChoiceField(queryset=Deporte.objects.all(), required=False,
                                       empty_label='Todas las categorías')
    entrega = forms.ChoiceField(required=False, choices=[('', 'Todos')] + list(Pedido.Entrega.choices))

