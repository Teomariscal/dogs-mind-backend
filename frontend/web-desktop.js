/* ═══════════════════════════════════════════════════════════════════════════
   THE DOGS' MIND — PANEL WEB DE ESCRITORIO
   Estructura propia (barra superior + rejilla bento). Las funciones de la app
   se conservan: cada tarjeta llama a la misma pantalla que ya existe.
   ---------------------------------------------------------------------------
   TRIPLE CIERRE DE SEGURIDAD (founder 2026-07-28):
     1. index.html solo carga este archivo si NO estamos en app nativa.
     2. Vuelve a comprobarlo aquí abajo y sale sin hacer NADA si detecta app.
     3. Todo lo que crea cuelga de body.dm-web + @media (min-width:1024px).

   COPY: los textos descriptivos son PROVISIONALES y de carácter funcional.
   El copy público (secciones institucionales) lo escribe el founder — por eso
   sus paneles salen con el hueco marcado en lugar de texto inventado.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  try {
    if (typeof window.dmIsNativeApp === 'function' && window.dmIsNativeApp()) return;
    if (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()) return;
    if (!document.body || !document.body.classList.contains('dm-web')) return;
  } catch (e) { return; }

  /* ── Iconografía: un solo set, trazo 1.75, 24×24 ───────────────────────── */
  var IC = {
    conducta: '<path d="M12 3a4 4 0 0 0-4 4v1.2A4 4 0 0 0 5 12v2a4 4 0 0 0 4 4h.5L12 21l2.5-3H15a4 4 0 0 0 4-4v-2a4 4 0 0 0-3-3.8V7a4 4 0 0 0-4-4Z"/><path d="M9.5 12h5"/>',
    entrenar: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    aigents:  '<path d="M12 3v2M5.6 5.6l1.4 1.4M3 12h2M18.4 5.6 17 7M21 12h-2"/><circle cx="12" cy="14" r="6"/><path d="M10 13h.01M14 13h.01M10.5 16.5h3"/>',
    registro: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    inspira:  '<path d="M12 3l1.9 4.6 4.6 1.9-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3Z"/><path d="M18 15l.9 2.1 2.1.9-2.1.9L18 21l-.9-2.1-2.1-.9 2.1-.9L18 15Z"/>',
    mundo:    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.7 3.8 9S14.5 18.4 12 21c-2.5-2.6-3.8-5.7-3.8-9S9.5 5.6 12 3Z"/>',
    novedad:  '<path d="M4 6h16M4 12h16M4 18h10"/><circle cx="19" cy="18" r="2"/>',
    suscribe: '<path d="M3 8h18v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 8l3-4h12l3 4M9 13h6"/>',
    cert:     '<circle cx="12" cy="9" r="5"/><path d="M8.5 13.5 7 21l5-2.5L17 21l-1.5-7.5"/>',
    proyecto: '<path d="M3 7h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    partners: '<circle cx="8" cy="9" r="3"/><circle cx="16" cy="9" r="3"/><path d="M3 19c0-2.8 2.2-5 5-5M21 19c0-2.8-2.2-5-5-5"/>',
    founders: '<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>',
    tour:     '<circle cx="12" cy="12" r="9"/><path d="M12 8v4l3 2"/>'
  };
  function svg(d) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ' +
           'stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>';
  }

  /* ── Barra superior ────────────────────────────────────────────────────── */
  var ACCIONES = [
    { label: 'Problema de conducta',      screen: 's-anamnesis' },
    { label: 'Educación y entrenamiento', screen: 's-anamnesis-training' },
    { label: 'The Dogs Aigents',          screen: 's-avatars' },
    { label: 'Inspiración Profesional',   screen: 's-training' },
    { label: 'Registros de conducta',     screen: 's-records' }
  ];
  var SECCIONES = [
    { label: 'World Wide Dog Walking',       panel: 'wwdw' },
    { label: 'Novedades',                    panel: 'novedades' },
    { label: 'Suscríbete a TDM',             panel: 'suscribete' },
    { label: 'TDM Certified Professionals',  panel: 'certified' },
    { label: 'Proyectos',                    panel: 'proyectos' },
    { label: 'Partners',                     panel: 'partners' },
    { label: 'Founders y Comité Científico', panel: 'founders' },
    { label: 'Tour',                         screen: 's-tour-intro' }
  ];

  /* ── Rejilla bento del panel ───────────────────────────────────────────── */
  var TARJETAS = [
    { h: 'Método' },
    { ic: IC.conducta, t: 'Problema de conducta',
      d: 'Anamnesis estructurada y análisis funcional del caso: antecedentes, conducta y consecuencias.',
      screen: 's-anamnesis', span: 4 },
    { ic: IC.entrenar, t: 'Educación y entrenamiento',
      d: 'Programa por fases con criterios de avance y registro diario del progreso.',
      screen: 's-anamnesis-training', span: 4 },
    { ic: IC.aigents, t: 'The Dogs Aigents',
      d: 'Consulta con los Aigents del equipo sobre el caso abierto.',
      screen: 's-avatars', span: 4 },

    { h: 'Tu trabajo' },
    { ic: IC.registro, t: 'Registros de conducta',
      d: 'Historial de casos, informes y seguimiento.',
      screen: 's-records', span: 6 },
    { ic: IC.inspira, t: 'Inspiración Profesional', tag: 'Profesional',
      d: 'Genera la sesión de trabajo de hoy a partir de tu objetivo.',
      screen: 's-training', span: 6 },

    { h: 'The Dogs’ Mind' },
    { ic: IC.suscribe, t: 'Suscríbete a TDM', panel: 'suscribete', span: 4 },
    { ic: IC.cert,     t: 'TDM Certified Professionals', panel: 'certified', span: 4 },
    { ic: IC.mundo,    t: 'World Wide Dog Walking', panel: 'wwdw', span: 4 },
    { ic: IC.proyecto, t: 'Proyectos',  panel: 'proyectos', span: 3 },
    { ic: IC.partners, t: 'Partners',   panel: 'partners',  span: 3 },
    { ic: IC.founders, t: 'Founders y Comité Científico', panel: 'founders', span: 3 },
    { ic: IC.novedad,  t: 'Novedades',  panel: 'novedades', span: 3 }
  ];

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }
  function irA(screenId) {
    cerrarPanel();
    try { if (typeof window.goTo === 'function') window.goTo(screenId); } catch (e) {}
  }

  function construirBarra() {
    var bar = el('header', 'dmw-bar');
    var inner = el('div', 'dmw-bar-in');
    var brand = el('button', 'dmw-brand',
      '<img src="assets/images/img-02.webp" alt="">' +
      '<span><b>The Dogs’ Mind</b><i>AI for Canine Behavior · by Teo Mariscal</i></span>');
    brand.onclick = function () { irA('s-home'); };
    inner.appendChild(brand);

    var nav = el('nav', 'dmw-nav');
    ACCIONES.forEach(function (b) {
      var n = el('button', 'dmw-btn dmw-btn-accion', b.label);
      n.onclick = function () { irA(b.screen); };
      nav.appendChild(n);
    });
    inner.appendChild(nav);
    bar.appendChild(inner);

    var row2 = el('div', 'dmw-bar2');
    var in2 = el('div', 'dmw-bar2-in');
    SECCIONES.forEach(function (b) {
      var n = el('button', 'dmw-btn dmw-btn-sec', b.label);
      n.onclick = function () { b.screen ? irA(b.screen) : abrirPanel(b.panel, b.label); };
      in2.appendChild(n);
    });
    row2.appendChild(in2);
    bar.appendChild(row2);
    document.body.appendChild(bar);
  }

  function construirPanelHome() {
    var home = document.getElementById('s-home');
    if (!home) return;
    var scroll = home.querySelector('div[style*="overflow-y:auto"]') || home.children[1];
    if (!scroll) return;

    /* Hero en vídeo (el de Inspiración Profesional) */
    var hero = el('section', 'dmw-hero',
      '<video class="dmw-hero-vid" autoplay muted loop playsinline>' +
        '<source src="assets/videos/inspiracion-hero.mp4" type="video/mp4">' +
      '</video>' +
      '<div class="dmw-hero-ov"></div>' +
      '<div class="dmw-hero-tx">' +
        '<div class="dmw-hero-eyebrow">Análisis funcional de la conducta</div>' +
        '<h1 class="dmw-hero-h1">AI for Canine Behavior</h1>' +
        '<p class="dmw-hero-p">Anamnesis, hipótesis funcional y plan de intervención con criterio clínico y métodos respetuosos (LIMA).</p>' +
        '<div class="dmw-hero-cta">' +
          '<button class="dmw-cta dmw-cta-1" data-go="s-anamnesis">Iniciar análisis</button>' +
          '<button class="dmw-cta dmw-cta-2" data-go="s-anamnesis-training">Educación y entrenamiento</button>' +
        '</div>' +
      '</div>');
    hero.querySelectorAll('[data-go]').forEach(function (b) {
      b.onclick = function () { irA(b.getAttribute('data-go')); };
    });
    /* El <source> se inyecta por innerHTML: hay que pedir la carga a mano. */
    var vid = hero.querySelector('.dmw-hero-vid');
    if (vid) {
      try { vid.load(); var p = vid.play(); if (p && p.catch) p.catch(function () {}); } catch (e) {}
    }

    /* Rejilla */
    var grid = el('div', 'dmw-grid');
    TARJETAS.forEach(function (c) {
      if (c.h) {
        grid.appendChild(el('div', 'dmw-sec-h', '<h2>' + c.h + '</h2>'));
        return;
      }
      var cls = 'dmw-card' + (c.span === 6 ? ' dmw-card-wide' : '') + (c.span === 12 ? ' dmw-card-full' : '');
      var card = el('button', cls,
        (c.tag ? '<span class="dmw-card-tag">' + c.tag + '</span>' : '') +
        '<span class="dmw-card-ic">' + svg(c.ic) + '</span>' +
        '<h3>' + c.t + '</h3>' +
        (c.d ? '<p>' + c.d + '</p>' : ''));
      if (c.span === 3) card.style.gridColumn = 'span 3';
      card.onclick = function () { c.screen ? irA(c.screen) : abrirPanel(c.panel, c.t); };
      grid.appendChild(card);
    });

    scroll.insertBefore(grid, scroll.firstChild);
    scroll.insertBefore(hero, scroll.firstChild);
  }

  /* ── Paneles de sección (copy pendiente del founder) ───────────────────── */
  function abrirPanel(id, titulo) {
    var ovl = document.getElementById('dmw-panel');
    if (!ovl) return;
    ovl.querySelector('.dmw-panel-title').textContent = titulo;
    ovl.querySelector('.dmw-panel-body').innerHTML =
      '<div class="dmw-hueco">' +
        '<div class="dmw-hueco-tag">Sección preparada</div>' +
        '<p>La estructura está lista y enlazada desde la barra y desde el panel. ' +
        'El contenido de esta sección — textos, imágenes, enlaces — lo defines tú. ' +
        'Dime qué va aquí y lo monto.</p>' +
      '</div>';
    ovl.classList.add('on');
    ovl.setAttribute('data-panel', id);
    document.addEventListener('keydown', escCerrar);
  }
  function cerrarPanel() {
    var ovl = document.getElementById('dmw-panel');
    if (ovl) ovl.classList.remove('on');
    document.removeEventListener('keydown', escCerrar);
  }
  function escCerrar(e) { if (e.key === 'Escape') cerrarPanel(); }
  window.dmwCerrarPanel = cerrarPanel;

  function construirOverlay() {
    var ovl = el('div', 'dmw-panel');
    ovl.id = 'dmw-panel';
    ovl.setAttribute('role', 'dialog');
    ovl.setAttribute('aria-modal', 'true');
    ovl.innerHTML =
      '<div class="dmw-panel-card">' +
        '<button class="dmw-panel-x" aria-label="Cerrar">&#10005;</button>' +
        '<h2 class="dmw-panel-title"></h2>' +
        '<div class="dmw-panel-body"></div>' +
      '</div>';
    ovl.querySelector('.dmw-panel-x').onclick = cerrarPanel;
    ovl.onclick = function (e) { if (e.target === ovl) cerrarPanel(); };
    document.body.appendChild(ovl);
  }

  function init() {
    if (document.querySelector('.dmw-bar')) return;   // idempotente
    construirBarra();
    construirOverlay();
    construirPanelHome();
  }

  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
})();
