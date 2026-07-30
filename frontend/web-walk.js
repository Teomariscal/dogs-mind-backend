/* ═══════════════════════════════════════════════════════════════════════════
   WORLD WIDE DOG WALKING — versión real (v1), solo WEB
   ---------------------------------------------------------------------------
   AISLAMIENTO (founder 2026-07-28, "prioridad máxima: no afectar a las apps"):
   este archivo lo carga web-desktop.js bajo demanda, y web-desktop.js solo
   existe si NO estamos en app nativa. Además vuelve a comprobarlo al arrancar.

   DATOS REALES, SIN CLAVES NI FACTURACIÓN:
     · Mapa      → OpenStreetMap (teselas CARTO dark)
     · Lugares   → Overpass API (parques, zonas de perros, veterinarios,
                   fuentes de agua, tiendas de animales) — datos OSM reales
     · Rutas     → OSRM perfil peatonal (routing.openstreetmap.de)
     · Ubicación → geolocalización del navegador o búsqueda por nombre
                   (Nominatim)
   Nada de esto se inventa: si un dato no existe en OSM, no se muestra.
   Google Maps podrá sustituir estas fuentes más adelante sin tocar la UI.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  try {
    if (typeof window.dmIsNativeApp === 'function' && window.dmIsNativeApp()) return;
    if (!document.body || !document.body.classList.contains('dm-web')) return;
  } catch (e) { return; }

  var LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  var LEAFLET_JS  = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  var OVERPASS    = 'https://overpass-api.de/api/interpreter';
  var OSRM        = 'https://routing.openstreetmap.de/routed-foot/route/v1/foot/';
  var NOMINATIM   = 'https://nominatim.openstreetmap.org/search';

  var TIPOS = {
    park:         { n: 'Zona verde',        c: '#7eb86a' },
    dog_park:     { n: 'Zona de perros',    c: '#7eb86a' },
    veterinary:   { n: 'Veterinario',       c: '#5ec8e6' },
    drinking_water:{ n: 'Fuente de agua',   c: '#5ec8e6' },
    pet:          { n: 'Tienda de animales',c: '#80d6ee' }
  };

  var mapa = null, capaRutas = null, capaPois = null, marcadorYo = null;
  var estado = { rutas: [], pois: [], centro: null };

  /* ── Utilidades ────────────────────────────────────────────────────────── */
  function cargar(url, tipo) {
    return new Promise(function (res, rej) {
      var e;
      if (tipo === 'css') { e = document.createElement('link'); e.rel = 'stylesheet'; e.href = url; }
      else { e = document.createElement('script'); e.src = url; }
      e.onload = res; e.onerror = rej;
      document.head.appendChild(e);
    });
  }
  function dist(a, b) {           // metros, haversine
    var R = 6371000, t = Math.PI / 180;
    var dLat = (b[0] - a[0]) * t, dLon = (b[1] - a[1]) * t;
    var x = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(a[0] * t) * Math.cos(b[0] * t) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(x));
  }
  function km(m) { return (m / 1000).toFixed(1).replace('.', ',') + ' km'; }
  function mins(m) { var v = Math.round(m / 1000 / 4.5 * 60); return v >= 60 ? Math.floor(v / 60) + ' h ' + (v % 60) + ' min' : v + ' min'; }

  /* ── Datos ─────────────────────────────────────────────────────────────── */
  async function buscarPois(lat, lon, radio) {
    var q = '[out:json][timeout:25];(' +
      'node["amenity"="veterinary"](around:' + radio + ',' + lat + ',' + lon + ');' +
      'node["amenity"="drinking_water"](around:' + radio + ',' + lat + ',' + lon + ');' +
      'node["shop"="pet"](around:' + radio + ',' + lat + ',' + lon + ');' +
      'node["leisure"="dog_park"](around:' + radio + ',' + lat + ',' + lon + ');' +
      'way["leisure"="dog_park"](around:' + radio + ',' + lat + ',' + lon + ');' +
      'way["leisure"="park"](around:' + radio + ',' + lat + ',' + lon + ');' +
      ');out center 80;';
    /* El servidor público de Overpass limita peticiones: si contesta con error
       o va saturado, reintentamos en el espejo antes de rendirnos. */
    var servidores = [OVERPASS, 'https://overpass.kumi.systems/api/interpreter'];
    var d = null, ultimo = '';
    for (var i = 0; i < servidores.length && !d; i++) {
      try {
        var r = await fetch(servidores[i], {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'data=' + encodeURIComponent(q)
        });
        if (!r.ok) { ultimo = 'HTTP ' + r.status; continue; }
        d = await r.json();
      } catch (e) { ultimo = e.message; }
    }
    if (!d) throw new Error(ultimo || 'overpass');
    return (d.elements || []).map(function (e) {
      var la = e.lat != null ? e.lat : (e.center && e.center.lat);
      var lo = e.lon != null ? e.lon : (e.center && e.center.lon);
      if (la == null) return null;
      var t = e.tags || {};
      var tipo = t.leisure === 'dog_park' ? 'dog_park'
               : t.leisure === 'park' ? 'park'
               : t.amenity === 'veterinary' ? 'veterinary'
               : t.amenity === 'drinking_water' ? 'drinking_water'
               : t.shop === 'pet' ? 'pet' : null;
      if (!tipo) return null;
      return { lat: la, lon: lo, tipo: tipo, nombre: t.name || TIPOS[tipo].n };
    }).filter(Boolean);
  }

  async function ruta(puntos) {          // puntos: [[lat,lon], …] — vuelve al inicio
    var coords = puntos.concat([puntos[0]]).map(function (p) { return p[1] + ',' + p[0]; }).join(';');
    var r = await fetch(OSRM + coords + '?overview=full&geometries=geojson');
    if (!r.ok) throw new Error('osrm');
    var d = await r.json();
    if (!d.routes || !d.routes.length) throw new Error('sin ruta');
    return {
      metros: d.routes[0].distance,
      linea: d.routes[0].geometry.coordinates.map(function (c) { return [c[1], c[0]]; })
    };
  }

  function elegirDestinos(pois, centro, objetivoM) {
    var r = objetivoM / 3.2;                       // radio aproximado del bucle
    var conD = pois.map(function (p) {
      return { p: p, d: dist([centro.lat, centro.lon], [p.lat, p.lon]) };
    }).filter(function (x) { return x.d > r * 0.35; });
    var verdes = conD.filter(function (x) { return x.p.tipo === 'park' || x.p.tipo === 'dog_park'; });
    var pool = (verdes.length ? verdes : conD).slice().sort(function (a, b) {
      return Math.abs(a.d - r) - Math.abs(b.d - r);
    });
    if (!pool.length) return null;
    var a = pool[0].p;
    var b = pool.find(function (x) { return dist([a.lat, a.lon], [x.p.lat, x.p.lon]) > r * 0.6; });
    var pts = [[centro.lat, centro.lon], [a.lat, a.lon]];
    if (b) pts.push([b.p.lat, b.p.lon]);
    return pts;
  }

  function poisEnRuta(pois, linea) {
    return pois.filter(function (p) {
      for (var i = 0; i < linea.length; i += 3) {
        if (dist([p.lat, p.lon], linea[i]) < 130) return true;
      }
      return false;
    });
  }

  /* ── Fotos de interés del camino ───────────────────────────────────────
     Wikimedia Commons: imágenes geolocalizadas (parques, monumentos,
     fuentes, edificios señalados). Gratis, sin clave y con autoría visible.
     Street View daría fotos de cualquier punto, pero exige cuenta de Google
     con facturación — se puede añadir después sin tocar esta interfaz. */
  var COMMONS = 'https://commons.wikimedia.org/w/api.php';

  async function fotosCerca(lat, lon, radio) {
    var u = COMMONS + '?action=query&format=json&origin=*' +
            '&generator=geosearch&ggsnamespace=6' +
            '&ggscoord=' + lat + '%7C' + lon +
            '&ggsradius=' + radio + '&ggslimit=8' +
            '&prop=imageinfo&iiprop=url%7Cextmetadata&iiurlwidth=360';
    var r = await fetch(u);
    if (!r.ok) return [];
    var d = await r.json();
    var pages = (d.query && d.query.pages) || {};
    return Object.keys(pages).map(function (k) {
      var p = pages[k], ii = p.imageinfo && p.imageinfo[0];
      if (!ii || !ii.thumburl) return null;
      var meta = ii.extmetadata || {};
      var autor = (meta.Artist && meta.Artist.value || '').replace(/<[^>]*>/g, '').trim();
      return {
        src: ii.thumburl,
        pagina: ii.descriptionurl,
        titulo: (p.title || '').replace(/^File:/, '').replace(/\.[a-z]+$/i, '').replace(/_/g, ' '),
        autor: autor.slice(0, 40)
      };
    }).filter(Boolean);
  }

  async function pintarFotos(rutaIdx) {
    var cont = document.getElementById('dmw-walk-fotos');
    if (!cont) return;
    var r = estado.rutas[rutaIdx];
    if (!r || !r.linea || !r.linea.length) { cont.innerHTML = ''; return; }
    cont.innerHTML = '<div class="dmw-fotos-cargando">Buscando fotos del camino…</div>';

    /* Tres puntos repartidos por la ruta: inicio, mitad y dos tercios */
    var idx = [0, Math.floor(r.linea.length * 0.4), Math.floor(r.linea.length * 0.7)];
    var vistas = {}, fotos = [];
    for (var i = 0; i < idx.length && fotos.length < 6; i++) {
      var p = r.linea[idx[i]];
      if (!p) continue;
      try {
        var lote = await fotosCerca(p[0], p[1], 350);
        lote.forEach(function (f) {
          if (!vistas[f.src] && fotos.length < 6) { vistas[f.src] = 1; fotos.push(f); }
        });
      } catch (e) { /* seguimos con el siguiente punto */ }
    }
    if (!fotos.length) {
      cont.innerHTML = '<div class="dmw-fotos-vacio">No hay fotos geolocalizadas de este recorrido.</div>';
      return;
    }
    cont.innerHTML =
      '<div class="dmw-fotos-h">Del camino · ' + fotos.length + ' fotos</div>' +
      '<div class="dmw-fotos-row">' + fotos.map(function (f) {
        return '<a class="dmw-foto" href="' + f.pagina + '" target="_blank" rel="noopener" title="' +
               f.titulo.replace(/"/g, '') + (f.autor ? ' — ' + f.autor.replace(/"/g, '') : '') + '">' +
                 '<img src="' + f.src + '" alt="' + f.titulo.replace(/"/g, '') + '" loading="lazy">' +
                 '<span>' + f.titulo + '</span>' +
               '</a>';
      }).join('') + '</div>' +
      '<div class="dmw-fotos-cred">Fotografías de Wikimedia Commons</div>';
  }

  /* ── Render ────────────────────────────────────────────────────────────── */
  /* ── Distancia que recorre el PERRO ────────────────────────────────────
     Base: Foltin & Ganslosser (30 perros, 120 paseos, 3.145 tramos con GPS).
     El perro suelto recorre una mediana de +1.000 m por paseo sobre su dueño,
     lo que el propio estudio cifra en un +43 %; cuartil bajo +400 m y alto
     +2.300 m. Convertidos a porcentaje sobre la misma distancia de referencia:
     +17 % / +43 % / +99 %. Atado, el perro hace tu misma distancia.
     NO se inventa nada: cada nivel corresponde a un cuartil publicado. */
  var NIVELES = {
    bajo:  { f: 1.17, n: 'Poco activo',  d: 'cuartil bajo del estudio' },
    medio: { f: 1.43, n: 'Normal',       d: 'mediana del estudio' },
    alto:  { f: 1.99, n: 'Muy activo',   d: 'cuartil alto del estudio' }
  };
  function nivelActual() {
    var v = 'medio';
    try { v = localStorage.getItem('dm_walk_nivel') || 'medio'; } catch (e) {}
    return NIVELES[v] ? v : 'medio';
  }
  function sueltoActual() {
    try { return localStorage.getItem('dm_walk_suelto') !== '0'; } catch (e) { return true; }
  }
  function metrosPerro(m) {
    return sueltoActual() ? m * NIVELES[nivelActual()].f : m;
  }

  function pintarLista(cont) {
    if (!estado.rutas.length) {
      cont.innerHTML = '<div class="dmw-walk-vacio">No hemos encontrado zonas verdes ni servicios ' +
        'suficientes en el entorno para proponer rutas. Prueba con otra ubicación.</div>';
      return;
    }
    cont.innerHTML = estado.rutas.map(function (r, i) {
      /* Agrupamos por tipo: cinco "Fuente de agua" seguidas no informan.
         Si el sitio tiene nombre propio y es único, se muestra el nombre. */
      var porTipo = {};
      r.pois.forEach(function (p) {
        (porTipo[p.tipo] = porTipo[p.tipo] || []).push(p);
      });
      var tags = Object.keys(porTipo).slice(0, 4).map(function (t) {
        var lista = porTipo[t];
        var conNombre = lista.filter(function (p) { return p.nombre !== TIPOS[t].n; });
        var txt = lista.length === 1
          ? (conNombre.length ? conNombre[0].nombre : TIPOS[t].n)
          : lista.length + ' · ' + TIPOS[t].n;
        return '<span class="ok">' + txt + '</span>';
      }).join('');
      var perro = metrosPerro(r.metros);
      var extra = perro > r.metros
        ? '<div class="dmw-perro-km"><b>' + km(perro) + '</b> recorrerá tu perro ' +
          '<span title="Estimación sobre datos publicados (Foltin &amp; Ganslosser)">estimado</span></div>'
        : '';
      return '<button class="dmw-ruta-c' + (i === 0 ? ' on' : '') + '" data-i="' + i + '">' +
               '<div class="dmw-ruta-top"><b>' + r.nombre + '</b><span>' + km(r.metros) + ' · ' + mins(r.metros) + '</span></div>' +
               '<p>' + r.por + '</p>' + extra +
               '<div class="dmw-ruta-tags">' + tags + '</div>' +
             '</button>';
    }).join('');
    cont.querySelectorAll('.dmw-ruta-c').forEach(function (b) {
      b.onclick = function () { seleccionar(parseInt(b.getAttribute('data-i'), 10)); };
    });
  }

  function seleccionar(i) {
    estado.rutas.forEach(function (r, j) {
      if (!r.capa) return;
      r.capa.setStyle({ color: j === i ? '#5ec8e6' : '#e8efea', opacity: j === i ? 1 : 0.25, weight: j === i ? 5 : 3 });
      if (j === i) { r.capa.bringToFront(); mapa.fitBounds(r.capa.getBounds(), { padding: [30, 30] }); }
    });
    document.querySelectorAll('#dmw-walk-lista .dmw-ruta-c').forEach(function (c, j) {
      c.classList.toggle('on', j === i);
    });
    pintarFotos(i);
  }

  function estadoTexto(t) {
    var e = document.getElementById('dmw-walk-estado');
    if (e) e.textContent = t;
  }

  async function generar(centro, etiqueta) {
    estado.centro = centro;
    estadoTexto('Buscando zonas verdes y servicios…');
    capaRutas.clearLayers(); capaPois.clearLayers();
    estado.rutas = [];
    mapa.setView([centro.lat, centro.lon], 15);
    if (marcadorYo) mapa.removeLayer(marcadorYo);
    marcadorYo = L.circleMarker([centro.lat, centro.lon], {
      radius: 8, color: '#fff', weight: 3, fillColor: '#5ec8e6', fillOpacity: 1
    }).addTo(mapa).bindTooltip(etiqueta || 'Estáis aquí');

    var pois;
    try { pois = await buscarPois(centro.lat, centro.lon, 1600); }
    catch (e) { estadoTexto('No se han podido consultar los datos del mapa. Inténtalo en un minuto.'); return; }
    estado.pois = pois;

    pois.forEach(function (p) {
      L.circleMarker([p.lat, p.lon], {
        radius: 5, color: TIPOS[p.tipo].c, weight: 2, fillColor: TIPOS[p.tipo].c, fillOpacity: .55
      }).bindTooltip(p.nombre + ' · ' + TIPOS[p.tipo].n).addTo(capaPois);
    });

    estadoTexto('Calculando rutas a pie…');
    var objetivos = [
      { nombre: 'Vuelta corta',  m: 1500, por: 'Paseo rápido por el entorno cercano.' },
      { nombre: 'Ruta media',    m: 3000, por: 'Equilibrio entre distancia y zonas verdes.' },
      { nombre: 'Ruta larga',    m: 5000, por: 'Para cuando tenéis tiempo y ganas de kilómetros.' }
    ];
    for (var k = 0; k < objetivos.length; k++) {
      var o = objetivos[k];
      var pts = elegirDestinos(pois, centro, o.m);
      if (!pts) continue;
      try {
        var res = await ruta(pts);
        var capa = L.polyline(res.linea, { color: '#e8efea', weight: 3, opacity: .25 }).addTo(capaRutas);
        estado.rutas.push({
          nombre: o.nombre, por: o.por, metros: res.metros, linea: res.linea,
          pois: poisEnRuta(pois, res.linea), capa: capa
        });
      } catch (e) { /* esa distancia no sale: seguimos con las demás */ }
    }
    pintarLista(document.getElementById('dmw-walk-lista'));
    estadoTexto(estado.rutas.length
      ? estado.rutas.length + ' rutas sobre datos reales de OpenStreetMap'
      : 'Sin rutas disponibles aquí.');
    if (estado.rutas.length) seleccionar(0);
  }

  /* ── Montaje ───────────────────────────────────────────────────────────── */
  async function montar(cont) {
    cont.innerHTML =
      '<div class="dmw-walk">' +
        '<div class="dmw-walk-h">' +
          '<button class="dmw-walk-btn" id="dmw-walk-geo">Usar mi ubicación</button>' +
          '<div class="dmw-walk-sep">o</div>' +
          '<input class="dmw-walk-in" id="dmw-walk-q" placeholder="Escribe una ciudad o dirección…">' +
          '<button class="dmw-walk-btn alt" id="dmw-walk-go">Buscar</button>' +
        '</div>' +
        '<div class="dmw-walk-body">' +
          '<div id="dmw-walk-map" class="dmw-walk-map"></div>' +
          '<div class="dmw-rutas" id="dmw-walk-lista">' +
            '<div class="dmw-walk-vacio">Dinos dónde estáis y calculamos tres rutas a pie ' +
            'con las zonas verdes y los servicios que hay de verdad alrededor.</div>' +
          '</div>' +
        '</div>' +
        '<div class="dmw-walk-fotos" id="dmw-walk-fotos"></div>' +
        '<div class="dmw-perfil">' +
          '<div class="dmw-perfil-h">¿Cómo es tu perro?</div>' +
          '<div class="dmw-perfil-ops" id="dmw-perfil-ops">' +
            Object.keys(NIVELES).map(function (k) {
              return '<button data-n="' + k + '">' + NIVELES[k].n + '</button>';
            }).join('') +
          '</div>' +
          '<label class="dmw-suelto"><input type="checkbox" id="dmw-suelto"> Va suelto durante el paseo</label>' +
          '<div class="dmw-perfil-nota" id="dmw-perfil-nota"></div>' +
        '</div>' +
        '<div class="dmw-walk-f"><span id="dmw-walk-estado">Datos de OpenStreetMap · rutas a pie por OSRM</span></div>' +
      '</div>';

    if (!window.L) {
      try { await cargar(LEAFLET_CSS, 'css'); await cargar(LEAFLET_JS, 'js'); }
      catch (e) { estadoTexto('No se ha podido cargar el mapa.'); return; }
    }
    mapa = L.map('dmw-walk-map', { zoomControl: true, attributionControl: true })
            .setView([40.4168, -3.7038], 13);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap · © CARTO', maxZoom: 19
    }).addTo(mapa);
    capaRutas = L.layerGroup().addTo(mapa);
    capaPois  = L.layerGroup().addTo(mapa);

    /* Perfil del perro: nivel de actividad + si va suelto */
    var ops = document.getElementById('dmw-perfil-ops');
    var chk = document.getElementById('dmw-suelto');
    var nota = document.getElementById('dmw-perfil-nota');
    function pintaPerfil() {
      var n = nivelActual(), s = sueltoActual();
      ops.querySelectorAll('button').forEach(function (b) {
        b.classList.toggle('on', b.getAttribute('data-n') === n);
      });
      chk.checked = s;
      nota.innerHTML = s
        ? 'Suelto y ' + NIVELES[n].n.toLowerCase() + ': tu perro recorre alrededor de un <b>' +
          Math.round((NIVELES[n].f - 1) * 100) + ' %</b> más que tú (' + NIVELES[n].d + ').'
        : 'Atado a tu lado recorre <b>tu misma distancia</b>. Marca la casilla si va suelto.';
      if (estado.rutas.length) pintarLista(document.getElementById('dmw-walk-lista'));
    }
    ops.querySelectorAll('button').forEach(function (b) {
      b.onclick = function () {
        try { localStorage.setItem('dm_walk_nivel', b.getAttribute('data-n')); } catch (e) {}
        pintaPerfil();
      };
    });
    chk.onchange = function () {
      try { localStorage.setItem('dm_walk_suelto', chk.checked ? '1' : '0'); } catch (e) {}
      pintaPerfil();
    };
    pintaPerfil();

    document.getElementById('dmw-walk-geo').onclick = function () {
      estadoTexto('Pidiendo tu ubicación…');
      if (!navigator.geolocation) { estadoTexto('Tu navegador no da la ubicación.'); return; }
      navigator.geolocation.getCurrentPosition(
        function (p) { generar({ lat: p.coords.latitude, lon: p.coords.longitude }, 'Estáis aquí'); },
        function () { estadoTexto('No nos has dado permiso de ubicación. Escribe una ciudad.'); },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    };
    var buscar = async function () {
      var q = (document.getElementById('dmw-walk-q').value || '').trim();
      if (!q) return;
      estadoTexto('Buscando «' + q + '»…');
      try {
        var r = await fetch(NOMINATIM + '?format=json&limit=1&q=' + encodeURIComponent(q));
        var d = await r.json();
        if (!d.length) { estadoTexto('No hemos encontrado ese sitio.'); return; }
        generar({ lat: parseFloat(d[0].lat), lon: parseFloat(d[0].lon) }, d[0].display_name.split(',')[0]);
      } catch (e) { estadoTexto('No se ha podido buscar ese sitio.'); }
    };
    document.getElementById('dmw-walk-go').onclick = buscar;
    document.getElementById('dmw-walk-q').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') buscar();
    });
  }

  window.dmwWalkMontar = montar;
})();
