/* E-SportGP - Interacciones con SweetAlert2 */
(function () {
  'use strict';

  const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3500,
    timerProgressBar: true,
    didOpen: (t) => {
      t.addEventListener('mouseenter', Swal.stopTimer);
      t.addEventListener('mouseleave', Swal.resumeTimer);
    },
  });

  const titulos = {
    success: 'Listo',
    error: 'Error',
    warning: 'Atención',
    info: 'Información',
  };

  function leerJSON(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function escapar(texto) {
    const div = document.createElement('div');
    div.textContent = texto;
    return div.innerHTML;
  }

  /* 1. Mensajes del framework de Django */
  function mostrarMensajes() {
    const mensajes = leerJSON('django-mensajes') || [];
    mensajes.forEach((m, i) => {
      const icon = titulos[m.nivel] ? m.nivel : 'info';
      if (icon === 'error') {
        // Los errores se muestran como modal para que no pasen desapercibidos
        Swal.fire({ icon, title: titulos[icon], text: m.texto, confirmButtonText: 'Entendido' });
      } else {
        setTimeout(() => Toast.fire({ icon, title: m.texto }), i * 400);
      }
    });
  }

  /* 2. Errores de formularios */
  function mostrarErroresFormulario() {
    const errores = leerJSON('form-errores');
    if (!errores || !errores.length) return;
    const lista = errores
      .map((e) => `<li class="list-group-item"><i class="bi bi-x-circle text-danger me-2"></i>${escapar(e)}</li>`)
      .join('');
    Swal.fire({
      icon: 'error',
      title: 'Revisa el formulario',
      html: `<ul class="list-group list-group-flush text-start small">${lista}</ul>`,
      confirmButtonText: 'Corregir',
    });
  }

  /* 3. Confirmaciones: <form data-confirm="texto"> o <a data-confirm="texto"> */
  function activarConfirmaciones() {
    document.addEventListener('submit', (ev) => {
      const form = ev.target;
      if (!form.dataset.confirm || form.dataset.confirmado) return;
      ev.preventDefault();
      Swal.fire({
        icon: form.dataset.confirmIcon || 'warning',
        title: form.dataset.confirmTitle || 'Confirmar accion',
        text: form.dataset.confirm,
        showCancelButton: true,
        reverseButtons: true,
        confirmButtonText: form.dataset.confirmOk || 'Sí, continuar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: form.dataset.confirmColor || '#dc3545',
        cancelButtonColor: '#6b7280',
      }).then((r) => {
        if (r.isConfirmed) {
          form.dataset.confirmado = '1';
          form.requestSubmit ? form.requestSubmit() : form.submit();
        }
      });
    });
  }

  /* 4. Validacion del navegador con Bootstrap + aviso SweetAlert2 */
  function activarValidacionCliente() {
    document.querySelectorAll('form.needs-validation').forEach((form) => {
      form.addEventListener('submit', (ev) => {
        if (!form.checkValidity()) {
          ev.preventDefault();
          ev.stopImmediatePropagation();
          form.classList.add('was-validated');
          Toast.fire({ icon: 'warning', title: 'Completa los campos requeridos' });
        }
      }, true);
    });
  }

  /* 5. Indicador de carga en botones de envio */
  function activarCargando() {
    document.addEventListener('submit', (ev) => {
      if (ev.defaultPrevented) return;
      const btn = ev.target.querySelector('[data-loading]');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>${btn.dataset.loading}`;
      }
    });
  }

  /* 6. Mostrar / ocultar contrasena */
  function activarVerPassword() {
    document.addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-ver-password]');
      if (!btn) return;
      const input = btn.parentElement.querySelector('input');
      const visible = input.type === 'text';
      input.type = visible ? 'password' : 'text';
      btn.querySelector('i').className = visible ? 'bi bi-eye' : 'bi bi-eye-slash';
      btn.setAttribute('aria-label', visible ? 'Mostrar contraseña' : 'Ocultar contraseña');
    });
  }

  /* 7. Cancelar un formulario con datos: pedir confirmacion */
  function activarCancelar() {
    document.addEventListener('click', (ev) => {
      const link = ev.target.closest('[data-cancelar]');
      if (!link) return;
      const form = link.closest('form');
      const conDatos = form && [...form.elements].some((el) =>
        (el.type === 'checkbox' && el.checked) ||
        (['text', 'email', 'tel', 'password'].includes(el.type) && el.value.trim()));
      if (!conDatos) return;
      ev.preventDefault();
      Swal.fire({
        icon: 'warning',
        title: '¿Salir sin terminar?',
        text: 'Los datos que ingresaste se perderán.',
        showCancelButton: true,
        reverseButtons: true,
        confirmButtonText: 'Sí, salir',
        cancelButtonText: 'Seguir aquí',
        confirmButtonColor: '#1f5bd8',
      }).then((r) => { if (r.isConfirmed) window.location.href = link.href; });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    activarVerPassword();
    activarCancelar();
    activarValidacionCliente();
    activarConfirmaciones();
    activarCargando();
    mostrarMensajes();
    mostrarErroresFormulario();
  });
})();
