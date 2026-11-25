/* SportPG - Ficha de producto: galeria, variantes (talla/color), cantidad y carrito */
(function () {
  'use strict';

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
  const leer = (id) => JSON.parse(document.getElementById(id).textContent);
  const escapar = (t) => { const d = document.createElement('div'); d.textContent = t ?? ''; return d.innerHTML; };

  const cfg = $('[data-pd-config]').dataset;
  const variantes = leer('pd-variantes');
  const guia = leer('pd-guia');
  const esCalzado = cfg.calzado === '1';
  const POCAS = 5;

  const tallas = [...new Set(variantes.map((v) => v.talla).filter(Boolean))];
  const colores = [...new Set(variantes.map((v) => v.color).filter(Boolean))];
  const estado = { talla: null, color: null, cantidad: 1 };

  /* ---------- Galeria ---------- */
  const minis = $$('.pd-mini');
  let fotoActual = 0;
  function mostrarFoto(i) {
    if (!minis.length) return;
    fotoActual = (i + minis.length) % minis.length;
    const m = minis[fotoActual];
    const img = $('[data-foto-principal]');
    img.src = m.dataset.url;
    img.alt = `${cfg.producto} - ${m.dataset.etiqueta}`;
    minis.forEach((x, j) => x.classList.toggle('activa', j === fotoActual));
    $('[data-foto-num]').textContent = String(fotoActual + 1).padStart(2, '0');
    $('[data-foto-etiqueta]').textContent = m.dataset.etiqueta;
  }
  minis.forEach((m, i) => m.addEventListener('click', () => mostrarFoto(i)));
  $$('[data-paso]').forEach((b) => b.addEventListener('click', () => mostrarFoto(fotoActual + Number(b.dataset.paso))));

  /* ---------- Variantes ---------- */
  const stockDe = (talla, color) => variantes
    .filter((v) => (!talla || v.talla === talla) && (!color || v.color === color))
    .reduce((s, v) => s + v.stock, 0);
  const varianteActual = () => variantes.find((v) => v.talla === estado.talla && v.color === estado.color);
  const etiquetaTalla = (t) => (esCalzado ? `${t} cm` : t);

  function elegirTalla(t) {
    estado.talla = t;
    if (colores.length && stockDe(t, estado.color) === 0) {
      estado.color = colores.find((c) => stockDe(t, c) > 0) || estado.color;
    }
    render();
  }

  function elegirColor(c) {
    estado.color = c;
    if (tallas.length && stockDe(estado.talla, c) === 0) {
      estado.talla = tallas.find((t) => stockDe(t, c) > 0) || estado.talla;
    }
    render();
  }

  function render() {
    const v = varianteActual();
    const stock = v ? v.stock : 0;

    // Tallas
    const agotadas = [];
    $$('.pd-talla').forEach((b) => {
      const t = b.dataset.talla;
      const sinStock = stockDe(t, null) === 0;
      if (sinStock) agotadas.push(t);
      b.classList.toggle('agotada', sinStock);
      b.classList.toggle('sin-color', !sinStock && stockDe(t, estado.color) === 0);
      b.disabled = sinStock;
      const activa = t === estado.talla;
      b.classList.toggle('activa', activa);
      b.setAttribute('aria-checked', activa);
    });
    const ayudaTalla = $('[data-talla-ayuda]');
    if (ayudaTalla) {
      const partes = [];
      if (agotadas.length) partes.push(`${agotadas.join(', ')} agotada${agotadas.length > 1 ? 's' : ''}.`);
      if (estado.talla) partes.push(`Seleccionada: ${etiquetaTalla(estado.talla)}.`);
      ayudaTalla.textContent = partes.join(' ');
    }

    // Colores
    const coloresAgotados = [];
    $$('.pd-color').forEach((b) => {
      const c = b.dataset.color;
      const sinStock = stockDe(null, c) === 0;
      if (sinStock) coloresAgotados.push(c);
      b.classList.toggle('agotado', sinStock);
      b.disabled = sinStock;
      const activo = c === estado.color;
      b.classList.toggle('activo', activo);
      b.setAttribute('aria-checked', activo);
    });
    const nombreColor = $('[data-color-nombre]');
    if (nombreColor) nombreColor.textContent = estado.color || '';
    const ayudaColor = $('[data-color-ayuda]');
    if (ayudaColor) ayudaColor.textContent = coloresAgotados.length ? `${coloresAgotados.join(', ')} agotado` : '';

    // Estado de stock
    const titulo = $('[data-estado]');
    const detalle = $('[data-estado-detalle]');
    titulo.className = 'pd-estado__titulo';
    if (stock === 0) {
      titulo.textContent = 'Agotado';
      titulo.classList.add('text-secondary');
      detalle.textContent = 'Elige otra talla o color.';
    } else if (stock <= POCAS) {
      titulo.textContent = `Últimas ${stock} unidad${stock === 1 ? '' : 'es'}`;
      titulo.classList.add('estado--pocas');
      detalle.textContent = 'en la variante seleccionada';
    } else {
      titulo.textContent = 'Disponible';
      detalle.textContent = `${stock} unidades en la variante seleccionada`;
    }

    // Cantidad: el maximo descuenta lo que ya esta en el carrito
    const enCarrito = v ? v.en_carrito : 0;
    const maximo = Math.max(stock - enCarrito, 0);
    const input = $('#cantidad');
    input.max = Math.max(maximo, 1);
    estado.cantidad = Math.min(Math.max(1, estado.cantidad), Math.max(maximo, 1));
    input.value = estado.cantidad;
    let textoMax = '';
    if (stock && !maximo) textoMax = `Ya tienes las ${enCarrito} unidades disponibles en tu carrito`;
    else if (maximo) textoMax = `Máximo ${maximo} unidad${maximo === 1 ? '' : 'es'}${enCarrito ? ` (ya tienes ${enCarrito} en tu carrito)` : ''}`;
    $('[data-maximo]').textContent = textoMax;
    $('[data-cantidad="-1"]').disabled = !maximo || estado.cantidad <= 1;
    $('[data-cantidad="1"]').disabled = !maximo || estado.cantidad >= maximo;
    input.disabled = !maximo;

    // Boton
    const btn = $('[data-btn-agregar]');
    btn.disabled = !maximo;
    $('span', btn).textContent = !stock ? 'Agotado' : (maximo ? 'Agregar al carrito' : 'Sin unidades disponibles');
  }

  $$('.pd-talla').forEach((b) => b.addEventListener('click', () => elegirTalla(b.dataset.talla)));
  $$('.pd-color').forEach((b) => b.addEventListener('click', () => elegirColor(b.dataset.color)));

  /* ---------- Cantidad ---------- */
  $$('[data-cantidad]').forEach((b) => b.addEventListener('click', () => {
    estado.cantidad += Number(b.dataset.cantidad);
    render();
  }));
  $('#cantidad').addEventListener('change', (e) => {
    estado.cantidad = parseInt(e.target.value, 10) || 1;
    render();
  });

  /* ---------- Guia de tallas (SweetAlert2) ---------- */
  const btnGuia = $('[data-guia-tallas]');
  if (btnGuia && guia) {
    btnGuia.addEventListener('click', () => {
      const filas = guia.filas.map((f) => `
        <tr class="${f[0] === estado.talla ? 'activa' : ''}">${f.map((c) => `<td>${escapar(c)}</td>`).join('')}</tr>`).join('');
      Swal.fire({
        html: `
          <div class="swal-sp__eyebrow">${escapar(guia.titulo)}</div>
          <h2 class="swal-sp__h">Encuentra tu ajuste ideal</h2>
          <p class="swal-sp__p">${escapar(guia.subtitulo)}</p>
          <div class="swal-sp__tabla">
            <table>
              <thead><tr>${guia.columnas.map((c) => `<th>${escapar(c)}</th>`).join('')}</tr></thead>
              <tbody>${filas}</tbody>
            </table>
          </div>
          <p class="swal-sp__nota">${escapar(guia.nota)}</p>`,
        width: 640,
        showCloseButton: true,
        closeButtonHtml: '<i class="bi bi-x-lg"></i>',
        confirmButtonText: 'Entendido',
        buttonsStyling: false,
        customClass: { popup: 'swal-sp', htmlContainer: 'swal-sp__html', actions: 'swal-sp__acciones',
                       confirmButton: 'btn btn-primary w-100', closeButton: 'swal-sp__cerrar' },
      });
    });
  }

  /* ---------- Agregar al carrito (fetch + SweetAlert2) ---------- */
  $('#form-agregar').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const v = varianteActual();
    if (!v || v.stock === 0) {
      Swal.fire({ icon: 'warning', title: 'Selecciona una variante', text: 'Elige una talla y color disponibles.' });
      return;
    }
    const form = ev.target;
    const btn = $('[data-btn-agregar]');
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Agregando';

    try {
      const datos = new FormData(form);
      datos.set('cantidad', estado.cantidad);
      const resp = await fetch(cfg.urlAgregar.replace('/0/', `/${v.id}/`), {
        method: 'POST',
        body: datos,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const json = await resp.json();
      if (!json.ok) throw new Error(json.mensaje);

      $$('.sp-badge').forEach((b) => { b.textContent = json.total_items; });
      v.en_carrito += json.cantidad;
      estado.cantidad = 1;
      Swal.fire({
        html: `
          <i class="bi bi-check2 swal-sp__check"></i>
          <h2 class="swal-sp__h">${escapar(json.mensaje)}</h2>
          <p class="swal-sp__p mb-0">${escapar(json.producto)}<br>${escapar(json.variante)}${json.cantidad > 1 ? ` &middot; ${json.cantidad} unidades` : ''}</p>`,
        width: 420,
        showDenyButton: true,
        confirmButtonText: 'Seguir comprando',
        denyButtonText: 'Ver carrito',
        buttonsStyling: false,
        customClass: { popup: 'swal-sp', htmlContainer: 'swal-sp__html', actions: 'swal-sp__acciones swal-sp__acciones--col',
                       confirmButton: 'btn btn-primary w-100', denyButton: 'btn btn-link w-100 swal-sp__secundario' },
      }).then((r) => { if (r.isDenied) window.location.href = cfg.urlCarrito; });
    } catch (err) {
      Swal.fire({ icon: 'error', title: 'No se pudo agregar', text: err.message || 'Intenta de nuevo.', confirmButtonText: 'Entendido' });
    } finally {
      btn.innerHTML = original;
      render();
    }
  });

  /* ---------- Seleccion inicial ---------- */
  // Color con mas unidades y, dentro de el, la talla del medio del rango (ej. 27) si tiene stock
  estado.color = colores.length
    ? colores.reduce((a, b) => (stockDe(null, b) > stockDe(null, a) ? b : a))
    : null;
  if (tallas.length) {
    const conStock = tallas.filter((t) => stockDe(t, estado.color) > 0);
    const media = tallas[Math.floor(tallas.length / 2)];
    estado.talla = conStock.includes(media) ? media : (conStock[0] || tallas[0]);
  }
  render();
})();
