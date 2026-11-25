import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Direccion, Perfil


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class LoginForm(BootstrapMixin, AuthenticationForm):
    username = forms.CharField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'autofocus': True, 'placeholder': 'nombre@correo.com',
                                       'autocomplete': 'email'}),
    )
    password = forms.CharField(
        label='Contraseña', strip=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Ingresa tu contraseña',
                                          'autocomplete': 'current-password'}),
    )
    error_messages = {
        'invalid_login': 'Correo o contraseña incorrectos.',
        'inactive': 'Esta cuenta está inactiva.',
    }


def validar_password(password, usuario=None):
    errores = []
    if len(password) < 8:
        errores.append('Debe tener al menos 8 caracteres.')
    if not re.search(r'[A-Z]', password):
        errores.append('Debe incluir al menos una mayúscula.')
    if not re.search(r'\d', password):
        errores.append('Debe incluir al menos un número.')
    if errores:
        raise forms.ValidationError(errores)
    password_validation.validate_password(password, usuario)


class RegistroForm(BootstrapMixin, forms.Form):
    first_name = forms.CharField(label='Nombre', max_length=150,
                                 widget=forms.TextInput(attrs={'placeholder': 'Tu nombre', 'autocomplete': 'given-name'}))
    last_name = forms.CharField(label='Apellido', max_length=150,
                                widget=forms.TextInput(attrs={'placeholder': 'Tu apellido', 'autocomplete': 'family-name'}))
    email = forms.EmailField(label='Correo electrónico',
                             widget=forms.EmailInput(attrs={'placeholder': 'nombre@correo.com', 'autocomplete': 'email'}))
    telefono = forms.CharField(label='Teléfono', max_length=20,
                               widget=forms.TextInput(attrs={'placeholder': '+507 6000-0000', 'autocomplete': 'tel'}))
    password = forms.CharField(label='Contraseña', strip=False,
                               help_text='Mínimo 8 caracteres, una mayúscula y un número.',
                               widget=forms.PasswordInput(attrs={'placeholder': 'Crea una contraseña segura',
                                                                 'autocomplete': 'new-password'}))
    terminos = forms.BooleanField(
        label='Acepto los términos y condiciones y el aviso de privacidad.',
        error_messages={'required': 'Debes aceptar los términos y condiciones.'},
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def clean_telefono(self):
        tel = re.sub(r'[\s\-()]', '', self.cleaned_data['telefono'])
        if not re.fullmatch(r'\+?\d{7,15}', tel):
            raise forms.ValidationError('Ingresa un teléfono válido.')
        return tel

    def clean(self):
        cd = super().clean()
        if cd.get('password'):
            usuario = User(username=cd.get('email', ''), email=cd.get('email', ''),
                           first_name=cd.get('first_name', ''), last_name=cd.get('last_name', ''))
            try:
                validar_password(cd['password'], usuario)
            except forms.ValidationError as e:
                self.add_error('password', e)
        return cd

    def save(self):
        cd = self.cleaned_data
        usuario = User.objects.create_user(
            username=cd['email'], email=cd['email'], password=cd['password'],
            first_name=cd['first_name'], last_name=cd['last_name'])
        Perfil.objects.create(usuario=usuario, telefono=cd['telefono'], acepto_terminos=timezone.now())
        return usuario


class PerfilForm(BootstrapMixin, forms.ModelForm):
    telefono = forms.CharField(label='Teléfono', max_length=20, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {'first_name': 'Nombre', 'last_name': 'Apellido', 'email': 'Correo electrónico'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        perfil = getattr(self.instance, 'perfil', None)
        if perfil:
            self.fields['telefono'].initial = perfil.telefono

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def save(self, commit=True):
        usuario = super().save(commit)
        perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
        perfil.telefono = self.cleaned_data.get('telefono', '')
        perfil.save()
        return usuario


class DireccionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Direccion
        fields = ['alias', 'recibe', 'provincia', 'calle', 'apto', 'telefono',
                  'corregimiento', 'distrito', 'codigo_postal', 'predeterminada']
        labels = {'alias': 'Alias', 'apto': 'Apto. / Casa (opcional)', 'codigo_postal': 'Código postal'}
        widgets = {
            'alias': forms.TextInput(attrs={'placeholder': 'Casa, Oficina...'}),
            'recibe': forms.TextInput(attrs={'placeholder': 'Nombre y apellido', 'autocomplete': 'name'}),
            'calle': forms.TextInput(attrs={'placeholder': 'Vía Argentina, PH El Cangrejo', 'autocomplete': 'address-line1'}),
            'apto': forms.TextInput(attrs={'placeholder': '4B'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+507 6000-0000', 'autocomplete': 'tel'}),
            'corregimiento': forms.TextInput(attrs={'placeholder': 'Bella Vista'}),
            'distrito': forms.TextInput(attrs={'placeholder': 'Panamá'}),
            'codigo_postal': forms.TextInput(attrs={'placeholder': '0801', 'autocomplete': 'postal-code'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['provincia'].widget.attrs['class'] = 'form-select'

    def clean_telefono(self):
        tel = re.sub(r'[\s\-()]', '', self.cleaned_data['telefono'])
        if not re.fullmatch(r'\+?\d{7,15}', tel):
            raise forms.ValidationError('Ingresa un teléfono válido.')
        return tel
