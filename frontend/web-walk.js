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

  /* ── Render ────────────────────────────────────────────────────────────── */
  function pintarLista(cont) {
    if (!estado.rutas.length) {
      cont.innerHTML = '<div class="dmw-walk-vacio">No hemos encontrado zonas verdes ni servicios ' +
        'suficientes en el entorno para proponer rutas. Prueba con otra ubicación.</div>';
      return;
    }
    cont.innerHTML = estado.rutas.map(function (r, i) {
      var tags = r.pois.slice(0, 5).map(function (p) {
        return '<span class="ok">' + p.nombre + '</span>';
      }).join('');
      return '<button class="dmw-ruta-c' + (i === 0 ? ' on' : '') + '" data-i="' + i + '">' +
               '<div class="dmw-ruta-top"><b>' + r.nombre + '</b><span>' + km(r.metros) + ' · ' + mins(r.metros) + '</span></div>' +
               '<p>' + r.por + '</p>' +
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
          nombre: o.nombre, por: o.por, metros: res.metros,
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
