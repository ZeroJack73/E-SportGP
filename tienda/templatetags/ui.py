from django import template

register = template.Library()


@register.filter
def errores_form(form):
    """Lista de errores legibles para mostrarlos con SweetAlert2."""
    if not form or not form.errors:
        return []
    errores = []
    for nombre, lista in form.errors.items():
        etiqueta = form.fields[nombre].label if nombre in form.fields else ''
        for error in lista:
            errores.append(f'{etiqueta}: {error}' if etiqueta else error)
    return errores


@register.inclusion_tag('includes/campo.html')
def campo(field, icono='bi-pencil'):
    """Renderiza un campo con Bootstrap, icono y estado de validacion."""
    if field.errors:
        clases = field.field.widget.attrs.get('class', '')
        if 'is-invalid' not in clases:
            field.field.widget.attrs['class'] = f'{clases} is-invalid'.strip()
    return {'field': field, 'icono': icono}


@register.filter
def moneda(valor):
    try:
        return f'${float(valor):,.2f} USD'
    except (TypeError, ValueError):
        return valor


@register.filter
def mensajes_lista(messages):
    """Convierte los mensajes de Django en una lista serializable."""
    return [{'nivel': m.level_tag or 'info', 'texto': str(m)} for m in messages]


@register.inclusion_tag('includes/campo_simple.html')
def campo_simple(field, password=False, ayuda=True):
    """Campo sin icono lateral (pantallas de acceso). password=True agrega el boton de mostrar."""
    if field.errors:
        clases = field.field.widget.attrs.get('class', '')
        if 'is-invalid' not in clases:
            field.field.widget.attrs['class'] = f'{clases} is-invalid'.strip()
    return {'field': field, 'es_password': password, 'mostrar_ayuda': ayuda}


@register.filter
def estrellas(valor, total=5):
    """Convierte una calificacion (ej. 4.6) en una lista: llena / media / vacia."""
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return []
    resultado = []
    for i in range(1, total + 1):
        if valor >= i - 0.25:
            resultado.append('llena')
        elif valor >= i - 0.75:
            resultado.append('media')
        else:
            resultado.append('vacia')
    return resultado


@register.filter
def responsable(usuario):
    """Nombre visible de quien hizo una accion; 'Sistema' si no hay usuario."""
    if not usuario:
        return 'Sistema'
    return usuario.get_full_name() or usuario.email
