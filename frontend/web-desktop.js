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

    /* Saldo: sustituye al anillo de tokens de la home móvil (que en escritorio
       se oculta). Se refresca solo leyendo el contador que ya mantiene la app. */
    var saldo = el('button', 'dmw-saldo', '<b id="dmw-saldo-n">–</b><span>créditos</span>');
    saldo.onclick = function () { irA('s-tokens'); };
    inner.appendChild(saldo);
    var pinta = function () {
      var src = document.getElementById('tok-home');
      var n = document.getElementById('dmw-saldo-n');
      if (src && n) n.textContent = (src.textContent || '').trim() || '–';
    };
    pinta();
    setInterval(pinta, 2500);

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

    /* Franja inferior: la foto de grupo de los Aigents (la misma de la app),
       centrada y grande, enmarcada en verde-cyan. */
    var band = el('section', 'dmw-aigents',
      '<div class="dmw-aigents-h">' +
        '<h2>The Dogs Aigents</h2>' +
        '<button class="dmw-aigents-cta" data-go="s-avatars">Hablar con un Aigent</button>' +
      '</div>' +
      '<button class="dmw-aigents-ph" data-go="s-avatars" aria-label="The Dogs Aigents">' +
        '<img src="aigents-final.webp" alt="Los Aigents — Niaz, Ale, Leo, Katja, Mario, Borja y Cecilia con Maximus" loading="lazy">' +
      '</button>');
    band.querySelectorAll('[data-go]').forEach(function (b) {
      b.onclick = function () { irA(b.getAttribute('data-go')); };
    });
    scroll.appendChild(band);
  }

  /* ── Contenido de las secciones ─────────────────────────────────────────
     El copy es del founder. Lo que falta se queda en hueco a propósito. */
  var CONTENIDO = {
    wwdw: {
      claim: 'Pasea con tu perro.',
      proto: true,
      intro: 'Estés en la ciudad o en el país que estés, si estás con tu perro The Dogs’ Mind te ayuda a elegir la mejor ruta de paseo.',
      como: {
        t: 'Cómo funciona',
        pasos: [
          ['Tu ubicación', 'Google Maps sitúa dónde estáis tu perro y tú en ese momento.'],
          ['La IA decide', 'Analiza el entorno real: zonas verdes, servicios, sombra y riesgos.'],
          ['Tres rutas', 'La app te propone tres opciones, de distancias diferentes, y eliges la que mejor os venga hoy.']
        ]
      },
      bloques: [
        { t: 'La ruta te marca', tipo: 'bien', items: [
          ['Zonas verdes', IC.mundo],
          ['Clínicas veterinarias en la ruta', IC.cert],
          ['Zonas de perros', IC.entrenar],
          ['Fuentes de agua', IC.novedad],
          ['Tiendas, restaurantes y bares pet friendly', IC.proyecto],
          ['Tiendas de animales', IC.suscribe],
          ['Zonas de sombra', IC.inspira]
        ]},
        { t: 'Y te avisa de peligros y molestias', tipo: 'aviso', items: [
          ['Perros sueltos por la calle'],
          ['Tráfico denso'],
          ['Zonas de alta contaminación'],
          ['Zonas sin sombra en verano']
        ]}
      ],
      social: {
        t: 'Pasea acompañado',
        p: 'Si quieres pasear acompañado por otro contacto registrado en la app, solo tienes que dar acceso a otros usuarios para que te encuentren durante el paseo o contacten contigo antes para pasear a los perros juntos.',
        cita: 'La mejor forma de conocer esa ciudad o ese lugar que te interesa es con un «local» y su perro.'
      }
    }
  };

  function htmlSeccion(c) {
    var h = '<p class="dmw-claim">' + c.claim + '</p>' +
            '<p class="dmw-intro">' + c.intro + '</p>';
    if (c.como) {
      h += '<h3 class="dmw-h3">' + c.como.t + '</h3><div class="dmw-pasos">';
      h += c.como.pasos.map(function (p, i) {
        return '<div class="dmw-paso"><span class="dmw-paso-n">' + (i + 1) + '</span>' +
               '<b>' + p[0] + '</b><span>' + p[1] + '</span></div>';
      }).join('') + '</div>';
    }
    c.bloques.forEach(function (b) {
      h += '<h3 class="dmw-h3">' + b.t + '</h3>';
      if (b.tipo === 'bien') {
        h += '<div class="dmw-poi">' + b.items.map(function (it) {
          return '<div class="dmw-poi-i"><span class="dmw-poi-ic">' + svg(it[1]) + '</span>' + it[0] + '</div>';
        }).join('') + '</div>';
      } else {
        h += '<ul class="dmw-avisos">' + b.items.map(function (it) {
          return '<li>' + it[0] + '</li>';
        }).join('') + '</ul>';
      }
    });
    h += '<div class="dmw-social">' +
           '<h3 class="dmw-h3" style="margin-top:0">' + c.social.t + '</h3>' +
           '<p>' + c.social.p + '</p>' +
           '<blockquote class="dmw-cita">' + c.social.cita + '</blockquote>' +
         '</div>';
    if (c.proto) h += '<h3 class="dmw-h3">Pru&eacute;balo ahora</h3><div id="dmw-walk-host"></div>';
    return h;
  }

  /* ── Prototipo navegable de World Wide Dog Walking ─────────────────────
     DATOS DE EJEMPLO. Todavía no hay Google Maps ni IA detrás: sirve para
     decidir si el planteamiento encaja antes de construirlo de verdad. */
  var RUTAS = [
    { id: 'corta', nom: 'Vuelta corta', km: '1,2 km', min: '18 min',
      d: 'M 90 300 L 170 300 L 170 215 L 300 215 L 300 150 L 360 150',
      bien: ['2 zonas de sombra', 'Fuente de agua a mitad'], mal: [],
      why: 'Máxima sombra y agua. Ideal ahora, con calor y para un paseo rápido.' },
    { id: 'media', nom: 'Parque y vuelta', km: '2,8 km', min: '40 min',
      d: 'M 90 300 L 90 200 L 200 200 L 200 110 L 380 110 L 470 165 L 470 260 L 300 260 L 300 300 L 200 300 L 200 330 L 120 330 L 90 300',
      bien: ['Zona verde amplia', 'Zona de perros', 'Clínica veterinaria en ruta'],
      mal: ['Cruza una avenida con tráfico denso'],
      why: 'La más equilibrada: verde, servicios y distancia media.' },
    { id: 'larga', nom: 'Río y regreso', km: '4,5 km', min: '1 h 05',
      d: 'M 90 300 L 60 220 L 120 140 L 250 90 L 400 70 L 520 120 L 560 220 L 500 310 L 380 340 L 250 330 L 150 345 L 90 300',
      bien: ['Recorrido junto al río', 'Bares pet friendly'],
      mal: ['Tramo final sin sombra', 'Se han reportado perros sueltos'],
      why: 'Para cuando tenéis tiempo y ganas de kilómetros.' }
  ];
  var POIS = [
    { x: 200, y: 145, t: 'verde',  n: 'Parque de la Alameda' },
    { x: 430, y: 175, t: 'vet',    n: 'Clínica veterinaria' },
    { x: 250, y: 215, t: 'agua',   n: 'Fuente de agua' },
    { x: 330, y: 265, t: 'perros', n: 'Zona de perros' },
    { x: 145, y: 265, t: 'pet',    n: 'Café pet friendly' },
    { x: 470, y: 300, t: 'aviso',  n: 'Tráfico denso' },
    { x: 520, y: 130, t: 'aviso',  n: 'Sin sombra en verano' }
  ];
  var POI_COLOR = { verde: '#7eb86a', vet: '#5ec8e6', agua: '#5ec8e6',
                    perros: '#7eb86a', pet: '#7eb86a', aviso: '#d4a76a' };

  function htmlPrototipo() {
    var mapa =
      '<svg class="dmw-map" viewBox="0 0 640 400" role="img" aria-label="Mapa de ejemplo con rutas">' +
        '<defs>' +
          '<pattern id="dmwgrid" width="32" height="32" patternUnits="userSpaceOnUse">' +
            '<path d="M32 0H0V32" fill="none" stroke="rgba(94,200,230,.10)" stroke-width="1"/>' +
          '</pattern>' +
        '</defs>' +
        '<rect width="640" height="400" fill="#0a1a14"/>' +
        '<rect width="640" height="400" fill="url(#dmwgrid)"/>' +
        '<circle cx="200" cy="145" r="52" fill="rgba(126,184,106,.16)"/>' +
        '<circle cx="330" cy="265" r="34" fill="rgba(126,184,106,.12)"/>' +
        RUTAS.map(function (r) {
          return '<path class="dmw-ruta" data-r="' + r.id + '" d="' + r.d + '" fill="none" ' +
                 'stroke="#5ec8e6" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" opacity=".18"/>';
        }).join('') +
        POIS.map(function (p) {
          return '<g class="dmw-poi-m"><circle cx="' + p.x + '" cy="' + p.y + '" r="7" fill="' + POI_COLOR[p.t] + '" opacity=".9"/>' +
                 '<circle cx="' + p.x + '" cy="' + p.y + '" r="12" fill="none" stroke="' + POI_COLOR[p.t] + '" opacity=".35"/>' +
                 '<title>' + p.n + '</title></g>';
        }).join('') +
        '<g><circle cx="90" cy="300" r="9" fill="#fff"/><circle cx="90" cy="300" r="18" fill="none" stroke="#fff" opacity=".35"/>' +
        '<title>Estáis aquí</title></g>' +
      '</svg>';

    var lista = RUTAS.map(function (r, i) {
      return '<button class="dmw-ruta-c' + (i === 1 ? ' on' : '') + '" data-r="' + r.id + '">' +
               '<div class="dmw-ruta-top"><b>' + r.nom + '</b><span>' + r.km + ' · ' + r.min + '</span></div>' +
               '<p>' + r.why + '</p>' +
               '<div class="dmw-ruta-tags">' +
                 r.bien.map(function (b) { return '<span class="ok">' + b + '</span>'; }).join('') +
                 r.mal.map(function (m) { return '<span class="warn">' + m + '</span>'; }).join('') +
               '</div>' +
             '</button>';
    }).join('');

    return '<div class="dmw-proto">' +
             '<div class="dmw-proto-h">' +
               '<span class="dmw-proto-tag">Prototipo · datos de ejemplo</span>' +
               '<span class="dmw-proto-loc">Tu ubicación · ahora · 31°C</span>' +
             '</div>' +
             '<div class="dmw-proto-body">' + mapa + '<div class="dmw-rutas">' + lista + '</div></div>' +
           '</div>';
  }

  function cablearPrototipo(root) {
    var paths = root.querySelectorAll('.dmw-ruta');
    var cards = root.querySelectorAll('.dmw-ruta-c');
    function marcar(id) {
      paths.forEach(function (p) {
        var on = p.getAttribute('data-r') === id;
        p.setAttribute('opacity', on ? '1' : '.15');
        p.setAttribute('stroke', on ? '#5ec8e6' : '#e8efea');
        p.setAttribute('stroke-width', on ? '5' : '3');
      });
      cards.forEach(function (c) { c.classList.toggle('on', c.getAttribute('data-r') === id); });
    }
    cards.forEach(function (c) {
      c.onclick = function () { marcar(c.getAttribute('data-r')); };
      c.onmouseenter = function () { marcar(c.getAttribute('data-r')); };
    });
    marcar('media');
  }

  function abrirPanel(id, titulo) {
    var ovl = document.getElementById('dmw-panel');
    if (!ovl) return;
    ovl.querySelector('.dmw-panel-title').textContent = titulo;
    ovl.querySelector('.dmw-panel-body').innerHTML = CONTENIDO[id]
      ? htmlSeccion(CONTENIDO[id])
      : '<div class="dmw-hueco">' +
          '<div class="dmw-hueco-tag">Sección preparada</div>' +
          '<p>La estructura está lista y enlazada desde la barra y desde el panel. ' +
          'El contenido de esta sección — textos, imágenes, enlaces — lo defines tú. ' +
          'Dime qué va aquí y lo monto.</p>' +
        '</div>';
    ovl.classList.add('on');
    ovl.setAttribute('data-panel', id);
    ovl.querySelector('.dmw-panel-card').scrollTop = 0;
    /* World Wide Dog Walking: monta el planificador real (carga diferida) */
    var host = ovl.querySelector('#dmw-walk-host');
    if (host) {
      if (window.dmwWalkMontar) { window.dmwWalkMontar(host); }
      else {
        var s = document.createElement('script');
        s.src = 'web-walk.js?v=5';
        s.onload = function () { if (window.dmwWalkMontar) window.dmwWalkMontar(host); };
        document.head.appendChild(s);
      }
    }
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

  /* Solo pantalla grande: en la web desde el móvil el usuario debe ver la app
     tal cual, no la barra ni el hero de escritorio (que dependen de un CSS
     que allí no se activa). Se construye al cruzar el umbral, no antes. */
  var GRANDE = window.matchMedia('(min-width: 1024px)');

  function init() {
    if (!GRANDE.matches) return;
    if (document.querySelector('.dmw-bar')) return;   // idempotente
    construirBarra();
    construirOverlay();
    construirPanelHome();
  }

  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
  if (GRANDE.addEventListener) GRANDE.addEventListener('change', init);
  else if (GRANDE.addListener) GRANDE.addListener(init);
})();
