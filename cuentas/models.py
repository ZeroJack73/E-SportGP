from django.conf import settings
from django.db import models, transaction


class Perfil(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='perfil', on_delete=models.CASCADE)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    acepto_terminos = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = 'perfiles'

    def __str__(self):
        return f'Perfil de {self.usuario}'


class Direccion(models.Model):
    PROVINCIAS = [(p, p) for p in [
        'Bocas del Toro', 'Chiriquí', 'Coclé', 'Colón', 'Darién', 'Herrera', 'Los Santos',
        'Panamá', 'Panamá Oeste', 'Veraguas', 'Comarca Emberá-Wounaan', 'Comarca Guna Yala',
        'Comarca Ngäbe-Buglé',
    ]]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='direcciones', on_delete=models.CASCADE)
    alias = models.CharField(max_length=40, help_text='Ejemplo: Casa, Oficina')
    recibe = models.CharField('nombre de quien recibe', max_length=120)
    telefono = models.CharField('teléfono de contacto', max_length=20)
    calle = models.CharField('calle / vía y edificio', max_length=200)
    apto = models.CharField('apto. / casa', max_length=60, blank=True)
    corregimiento = models.CharField(max_length=100)
    distrito = models.CharField(max_length=100)
    provincia = models.CharField(max_length=40, choices=PROVINCIAS, default='Panamá')
    codigo_postal = models.CharField('código postal', max_length=10, blank=True)
    predeterminada = models.BooleanField('usar como dirección predeterminada', default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-predeterminada', 'creado']
        verbose_name = 'dirección'
        verbose_name_plural = 'direcciones'

    def __str__(self):
        return f'{self.alias} ({self.usuario})'

    @property
    def linea1(self):
        """Ej.: Vía Argentina, PH El Cangrejo, Apto. 4B · Bella Vista"""
        calle = self.calle
        if self.apto:
            apto = self.apto if self.apto.lower().startswith(('apto', 'casa', 'piso')) else f'Apto. {self.apto}'
            calle = f'{calle}, {apto}'
        return f'{calle} · {self.corregimiento}'

    @property
    def linea2(self):
        """Ej.: Panamá, Panamá 0801"""
        texto = f'{self.distrito}, {self.provincia}'
        return f'{texto} {self.codigo_postal}' if self.codigo_postal else texto

    def texto(self):
        return f'{self.linea1}\n{self.linea2}'

    @transaction.atomic
    def save(self, *args, **kwargs):
        otras = Direccion.objects.filter(usuario=self.usuario).exclude(pk=self.pk)
        if not otras.exists():
            self.predeterminada = True  # la primera direccion siempre es la predeterminada
        elif self.predeterminada:
            otras.update(predeterminada=False)
        super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        era_predeterminada, usuario = self.predeterminada, self.usuario
        resultado = super().delete(*args, **kwargs)
        if era_predeterminada:
            siguiente = Direccion.objects.filter(usuario=usuario).order_by('creado').first()
            if siguiente:
                Direccion.objects.filter(pk=siguiente.pk).update(predeterminada=True)
        return resultado
