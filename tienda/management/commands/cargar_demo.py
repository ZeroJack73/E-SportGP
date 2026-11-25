from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from tienda.models import (Categoria, Color, Deporte, Marca, MovimientoInventario, Opinion, Producto,
                           ProductoImagen, Talla, Variante)

IMG_DIR = Path(__file__).resolve().parents[2] / 'demo_img'

DEPORTES = [('Fútbol', 'bi-dribbble'), ('Running', 'bi-stopwatch'),
            ('Ciclismo', 'bi-bicycle'), ('Fitness', 'bi-heart-pulse')]
CATEGORIAS = [('Calzado', 'bi-person-walking'), ('Balones', 'bi-circle'),
              ('Ropa', 'bi-handbag'), ('Accesorios', 'bi-bag'),
              ('Protección', 'bi-shield-check'), ('Equipamiento', 'bi-box-seam')]
MARCAS = ['SportPG', 'Apex', 'Stride', 'Pulse']
TALLAS_ROPA = ['S', 'M', 'L', 'XL']
TALLAS_CALZADO = ['25', '26', '27', '28', '29']
COLORES = [('Negro', '#212529'), ('Gris', '#ADB5BD'), ('Blanco', '#FFFFFF'),
           ('Azul', '#1F5BD8'), ('Naranja', '#E8711F'), ('Lima', '#C6D92F')]

MATERIALES = {
    'Calzado': 'Upper de malla transpirable · Entresuela EVA · Suela de caucho',
    'Balones': 'Cubierta de poliuretano · Cámara de butilo · Costura térmica',
    'Ropa': 'Poliéster reciclado 88% · Elastano 12% · Secado rápido',
    'Protección': 'Carcasa de policarbonato · Núcleo EPS · Acolchado removible',
    'Accesorios': 'Materiales libres de BPA · Apto para lavavajillas',
    'Equipamiento': 'Hierro fundido · Recubrimiento de goma antideslizante',
}

DESCRIPCIONES = {
    'Tenis Running Velocity Pro': (
        'Ligeros, cómodos y listos para sumar kilómetros. Los Velocity Pro ofrecen '
        'amortiguación reactiva y una pisada estable para tu entrenamiento diario sobre asfalto.'),
}

C, R = TALLAS_CALZADO, TALLAS_ROPA

# nombre, deporte, categoria, marca, precio, nuevo, destacado, tallas, colores, stock, imagen
# stock: int = unidades por variante; dict = {(talla, color): unidades}, el resto queda en 0
PRODUCTOS = [
    ('Tenis Running Velocity Pro', 'Running', 'Calzado', 'SportPG', '120.00', True, True, C,
     ['Lima', 'Negro', 'Gris'],
     {('25', 'Lima'): 6, ('26', 'Lima'): 9, ('27', 'Lima'): 12, ('28', 'Lima'): 4,
      ('25', 'Negro'): 3, ('26', 'Negro'): 5, ('27', 'Negro'): 7, ('28', 'Negro'): 2},
     'tenis-running-velocity-pro'),
    ('Balón de fútbol Match 5', 'Fútbol', 'Balones', 'Apex', '50.00', False, True, [], ['Blanco', 'Naranja'], 20, 'balon-futbol-match-5'),
    ('Casco de ciclismo Aero', 'Ciclismo', 'Protección', 'Stride', '44.99', False, True, ['M', 'L'], ['Blanco', 'Negro'],
     {('M', 'Blanco'): 1, ('L', 'Negro'): 2}, 'casco-ciclismo-aero'),
    ('Mancuernas hexagonales 5 kg', 'Fitness', 'Equipamiento', 'SportPG', '29.99', False, True, [], ['Negro'], 30, 'mancuernas-hexagonales-5kg'),
    ('Top deportivo Flow', 'Fitness', 'Ropa', 'Pulse', '19.99', True, False, R, ['Negro', 'Gris'], 5, 'top-deportivo-flow'),
    ('Chaqueta de ciclismo Windbreak', 'Ciclismo', 'Ropa', 'Stride', '64.90', False, False, R, ['Negro'], 0, 'chaqueta-ciclismo-windbreak'),
    ('Tacos de fútbol Strike FG', 'Fútbol', 'Calzado', 'Apex', '89.90', True, False, C, ['Blanco', 'Naranja'], 3, 'tacos-strike-fg'),
    ('Balón de entrenamiento Pro', 'Fútbol', 'Balones', 'SportPG', '34.99', False, False, [], ['Blanco'], 50, 'balon-entrenamiento-pro'),
    ('Tenis Running Daily', 'Running', 'Calzado', 'Stride', '79.99', False, False, C, ['Negro', 'Blanco'], 4, 'tenis-running-daily'),
    ('Botella deportiva 750 ml', 'Running', 'Accesorios', 'Pulse', '12.00', False, False, [], ['Azul'], 70, 'botella-deportiva-750'),
    ('Camiseta running Breeze', 'Running', 'Ropa', 'Stride', '24.99', False, False, R, ['Negro', 'Azul'],
     {('M', 'Negro'): 2, ('L', 'Azul'): 2}, 'camiseta-running-breeze'),
    ('Casco MTB Enduro', 'Ciclismo', 'Protección', 'Apex', '139.00', True, False, ['M', 'L', 'XL'], ['Naranja', 'Negro'], 2, 'casco-mtb-enduro'),
    ('Short de ciclismo Ride', 'Ciclismo', 'Ropa', 'Pulse', '32.50', False, False, R, ['Azul', 'Negro'], 3, 'short-ciclismo-ride'),
    ('Bidón de ciclismo 600 ml', 'Ciclismo', 'Accesorios', 'SportPG', '9.99', False, False, [], ['Azul', 'Blanco'], 25, 'bidon-ciclismo-600'),
    ('Rack de mancuernas Pro', 'Fitness', 'Equipamiento', 'Apex', '499.00', False, False, [], ['Negro'], 2, 'rack-mancuernas'),
    ('Kettlebell 12 kg', 'Fitness', 'Equipamiento', 'SportPG', '39.90', False, False, [], ['Negro'], 12, 'kettlebell-12kg'),
    ('Kettlebell 16 kg', 'Fitness', 'Equipamiento', 'Apex', '49.90', False, False, [], ['Negro'], 0, 'kettlebell-16kg'),
    ('Shaker de proteína 600 ml', 'Fitness', 'Accesorios', 'Pulse', '9.99', True, False, [], ['Gris', 'Blanco'], 30, 'shaker-proteina'),
]

GALERIA = {
    'Tenis Running Velocity Pro': [
        ('tenis-running-velocity-pro-lateral', 'Vista lateral'),
        ('tenis-running-velocity-pro', 'Vista superior'),
        ('tenis-running-velocity-pro-trasera', 'Vista trasera'),
        ('tenis-running-velocity-pro-detalle', 'Detalle'),
    ],
}

OPINIONES = {
    'Tenis Running Velocity Pro': [
        ('Andrea M.', 5, 'Muy cómodos para correr a diario. La talla viene exacta.', True),
        ('Luis R.', 4, 'Buen agarre y peso ligero. Me hubiera gustado más amortiguación en el talón.', True),
        ('Carla P.', 5, 'Los uso para medio maratón y responden muy bien. Excelente compra.', True),
        ('Jorge T.', 5, 'Se sienten firmes en curvas y el material respira bien.', False),
        ('Mariela S.', 5, 'Llegaron rápido y la horma es cómoda desde el primer día.', True),
    ],
    'Balón de fútbol Match 5': [
        ('Diego A.', 5, 'Buen bote y resistente en cancha sintética.', True),
        ('Sofía L.', 4, 'Muy buen balón, conserva bien el aire.', True),
    ],
    'Mancuernas hexagonales 5 kg': [
        ('Ricardo V.', 5, 'No ruedan y el agarre es cómodo.', True),
    ],
}


class Command(BaseCommand):
    help = 'Carga catálogo de ejemplo: productos con variantes, galería, materiales y opiniones.'

    @transaction.atomic
    def handle(self, *args, **options):
        deportes = {n: Deporte.objects.get_or_create(nombre=n, defaults={'icono': ico, 'orden': i})[0]
                    for i, (n, ico) in enumerate(DEPORTES)}
        categorias = {n: Categoria.objects.get_or_create(nombre=n, defaults={'icono': ico})[0]
                      for n, ico in CATEGORIAS}
        marcas = {n: Marca.objects.get_or_create(nombre=n)[0] for n in MARCAS}
        tallas = {}
        for i, n in enumerate(TALLAS_ROPA):
            tallas[n] = Talla.objects.get_or_create(nombre=n, defaults={'grupo': 'ropa', 'orden': i})[0]
        for i, n in enumerate(TALLAS_CALZADO):
            tallas[n] = Talla.objects.get_or_create(nombre=n, defaults={'grupo': 'calzado', 'orden': i})[0]
        colores = {n: Color.objects.get_or_create(nombre=n, defaults={'hex': h, 'orden': i})[0]
                   for i, (n, h) in enumerate(COLORES)}

        creados = 0
        for (nombre, dep, cat, marca, precio, nuevo, destacado,
             t_list, c_list, stock, img) in PRODUCTOS:
            producto, es_nuevo_reg = Producto.objects.get_or_create(nombre=nombre, defaults={
                'deporte': deportes[dep],
                'categoria': categorias[cat],
                'marca': marcas[marca],
                'precio': Decimal(precio),
                'es_nuevo': nuevo,
                'destacado': destacado,
                'material': MATERIALES[cat],
                'descripcion': DESCRIPCIONES.get(nombre, (
                    f'{nombre} de {marca}, diseñado para rendir al máximo en {dep.lower()}. '
                    'Materiales resistentes y cómodos para entrenar y competir.')),
            })
            if not es_nuevo_reg:
                continue
            creados += 1

            # Variantes: combinaciones talla x color
            for t in (t_list or [None]):
                for c in (c_list or [None]):
                    unidades = stock.get((t, c), 0) if isinstance(stock, dict) else stock
                    v = Variante.objects.create(producto=producto, stock=0,
                                                talla=tallas.get(t), color=colores.get(c))
                    if unidades:
                        MovimientoInventario.registrar(v.pk, MovimientoInventario.Tipo.ENTRADA, unidades,
                                                       'Inventario inicial')

            # Imagen principal + galeria
            fotos = GALERIA.get(nombre, [(img, 'Vista principal')])
            for i, (archivo, etiqueta) in enumerate(fotos):
                ruta = IMG_DIR / f'{archivo}.jpg'
                if not ruta.exists():
                    continue
                with ruta.open('rb') as f:
                    if i == 0:
                        producto.etiqueta_imagen = etiqueta
                        producto.imagen.save(ruta.name, File(f), save=True)
                    else:
                        extra = ProductoImagen(producto=producto, etiqueta=etiqueta, orden=i)
                        extra.imagen.save(ruta.name, File(f), save=True)

            for autor, nota, texto, verificada in OPINIONES.get(nombre, []):
                Opinion.objects.create(producto=producto, nombre=autor, calificacion=nota,
                                       comentario=texto, verificada=verificada)

        self.stdout.write(self.style.SUCCESS(f'Datos de ejemplo cargados ({creados} productos nuevos).'))
