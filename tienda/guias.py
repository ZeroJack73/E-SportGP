"""Guias de tallas de referencia por grupo de talla."""

GUIAS = {
    'calzado': {
        'subtitulo': 'Mide tu pie del talón al dedo más largo, en centímetros.',
        'columnas': ['Talla MX', 'Largo del pie (cm)', 'US hombre'],
        'filas': {str(t): [str(t), f'{t}.0', str(t - 18)] for t in range(22, 32)},
        'nota': 'Si estás entre dos tallas, elige la mayor.',
    },
    'ropa': {
        'subtitulo': 'Mide el contorno de pecho y cintura sin apretar la cinta.',
        'columnas': ['Talla', 'Pecho (cm)', 'Cintura (cm)'],
        'filas': {
            'S': ['S', '86 - 94', '71 - 79'],
            'M': ['M', '94 - 102', '79 - 87'],
            'L': ['L', '102 - 110', '87 - 95'],
            'XL': ['XL', '110 - 118', '95 - 103'],
        },
        'nota': 'Si prefieres un ajuste holgado, elige una talla más.',
    },
}


def guia_para(producto, tallas):
    """Devuelve la guia del grupo de tallas del producto, solo con sus tallas."""
    if not tallas:
        return None
    grupo = tallas[0].grupo
    base = GUIAS.get(grupo)
    if not base:
        return None
    filas = [base['filas'][t.nombre] for t in tallas if t.nombre in base['filas']]
    return {
        'titulo': f'Guía de tallas · {producto.deporte.nombre}',
        'subtitulo': base['subtitulo'],
        'columnas': base['columnas'],
        'filas': filas,
        'nota': f"{base['nota']} Medidas de referencia para el modelo {producto.nombre}.",
    }
