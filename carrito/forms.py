from django import forms


class CantidadForm(forms.Form):
    cantidad = forms.IntegerField(min_value=1, initial=1, label='Cantidad',
                                  error_messages={'min_value': 'La cantidad mínima es 1.',
                                                  'invalid': 'Ingresa una cantidad válida.',
                                                  'required': 'Ingresa una cantidad.'})
    reemplazar = forms.BooleanField(required=False)
