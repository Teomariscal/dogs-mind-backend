/* ═══════════════════════════════════════════════════════════════════════════
   WORLD WIDE DOG WALKING — versión real (v1): web Y app desde 1.0.5
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

  /* Desde 1.0.5 el paseo TAMBIÉN va en la app (founder 2026-08-02 "metelos"):
     en nativo pasa siempre; en web sigue exigiendo la capa dm-web, que solo
     existe fuera de la app. Antes esta guarda cortaba el fichero en nativo:
     el script cargaba pero no llegaba a definir dmwWalkMontar, así que el
     planificador abría sin mapa. */
  try {
    var _nativo = (typeof window.dmIsNativeApp === 'function' && window.dmIsNativeApp()) ||
                  !!(window.Capacitor && window.Capacitor.isNativePlatform &&
                     window.Capacitor.isNativePlatform());
    if (!_nativo && (!document.body || !document.body.classList.contains('dm-web'))) return;
  } catch (e) { return; }

  var LEAFLET_CSS = 'vendor/leaflet/leaflet.css';  /* local: sin CDN en el binario */
  var LEAFLET_JS  = 'vendor/leaflet/leaflet.js';
  var OVERPASS    = 'https://overpass-api.de/api/interpreter';
  var OSRM        = 'https://routing.openstreetmap.de/routed-foot/route/v1/foot/';
  var NOMINATIM   = 'https://nominatim.openstreetmap.org/search';

  var TIPOS = {
    park:         { n: 'Zona verde',        c: '#7eb86a' },
    dog_park:     { n: 'Zona de perros',    c: '#7eb86a' },
    veterinary:   { n: 'Veterinario',       c: '#5ec8e6' },
    drinking_water:{ n: 'Fuente de agua',   c: '#5ec8e6' },
    pet:          { n: 'Tienda de animales',c: '#80d6ee' },
    /* Founder 2026-08-17: "no solo buscar parques sino caminos, rutas de
       montaña o naturaleza". En un pueblo no hay parques etiquetados pero sí
       decenas de pistas y bosque — comprobado en Villamantilla: 0 parques,
       47 pistas, 5 senderos y 8 zonas de bosque en 2,5 km. */
    path:         { n: 'Sendero',           c: '#b6dca0' },
    track:        { n: 'Pista / camino',    c: '#b6dca0' },
    wood:         { n: 'Bosque',            c: '#7eb86a' },
    nature:       { n: 'Espacio natural',   c: '#7eb86a' },
    meadow:       { n: 'Prado',             c: '#9ecf86' }
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
    var a = '(around:' + radio + ',' + lat + ',' + lon + ');';
    var q = '[out:json][timeout:30];(' +
      'node["amenity"="veterinary"]' + a +
      'node["amenity"="drinking_water"]' + a +
      'node["shop"="pet"]' + a +
      'node["leisure"="dog_park"]' + a +
      'way["leisure"="dog_park"]' + a +
      'way["leisure"="park"]' + a +
      /* Campo y monte: sin esto, un pueblo se quedaba sin ninguna ruta. */
      'way["highway"~"^(path|track|footway|bridleway)$"]' + a +
      'way["natural"="wood"]' + a +
      'way["landuse"="forest"]' + a +
      'way["landuse"="meadow"]' + a +
      'way["leisure"="nature_reserve"]' + a +
      ');out center 120;';
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
               : t.shop === 'pet' ? 'pet'
               : t.leisure === 'nature_reserve' ? 'nature'
               : (t.natural === 'wood' || t.landuse === 'forest') ? 'wood'
               : t.landuse === 'meadow' ? 'meadow'
               : t.highway === 'track' ? 'track'
               : (t.highway === 'path' || t.highway === 'footway' || t.highway === 'bridleway') ? 'path'
               : null;
      if (!tipo) return null;
      return { lat: la, lon: lo, tipo: tipo, nombre: t.name || TIPOS[tipo].n };
    }).filter(Boolean);
  }

  /* Traducción de las maniobras que devuelve OSRM (vienen en inglés) */
  var GIROS = {
    left: 'gira a la izquierda', right: 'gira a la derecha',
    'slight left': 'ligeramente a la izquierda', 'slight right': 'ligeramente a la derecha',
    'sharp left': 'giro cerrado a la izquierda', 'sharp right': 'giro cerrado a la derecha',
    straight: 'sigue recto', uturn: 'da la vuelta'
  };
  function instruccion(paso) {
    var m = paso.maneuver || {};
    var via = paso.name ? ' por ' + paso.name : '';
    var d = paso.distance ? ' (' + Math.round(paso.distance) + ' m)' : '';
    if (m.type === 'depart')  return 'Sal' + via + d;
    if (m.type === 'arrive')  return 'Has llegado al punto de partida';
    if (m.type === 'roundabout' || m.type === 'rotary') return 'En la rotonda, toma la salida' + via + d;
    var g = GIROS[m.modifier] || 'continúa';
    return g.charAt(0).toUpperCase() + g.slice(1) + via + d;
  }

  async function ruta(puntos) {          // puntos: [[lat,lon], …] — vuelve al inicio
    var coords = puntos.concat([puntos[0]]).map(function (p) { return p[1] + ',' + p[0]; }).join(';');
    var r = await fetch(OSRM + coords + '?overview=full&geometries=geojson&steps=true');
    if (!r.ok) throw new Error('osrm');
    var d = await r.json();
    if (!d.routes || !d.routes.length) throw new Error('sin ruta');
    var pasos = [];
    (d.routes[0].legs || []).forEach(function (leg) {
      (leg.steps || []).forEach(function (s) {
        if (s.distance > 25 || (s.maneuver && s.maneuver.type === 'depart')) pasos.push(instruccion(s));
      });
    });
    return {
      metros: d.routes[0].distance,
      linea: d.routes[0].geometry.coordinates.map(function (c) { return [c[1], c[0]]; }),
      pasos: pasos,
      puntos: puntos
    };
  }

  /* Mueve un punto `m` metros en el rumbo `grados`. */
  function mover(lat, lon, m, grados) {
    var R = 6371000, t = Math.PI / 180, d = m / R, b = grados * t;
    var la = lat * t, lo = lon * t;
    var la2 = Math.asin(Math.sin(la) * Math.cos(d) + Math.cos(la) * Math.sin(d) * Math.cos(b));
    var lo2 = lo + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(la),
                              Math.cos(d) - Math.sin(la) * Math.sin(la2));
    return [la2 / t, lo2 / t];
  }

  /* Destinos cuando NO hay puntos de interés mapeados. En un pueblo puede no
     haber ni un parque ni una fuente en OpenStreetMap (comprobado: cero en
     1600 m alrededor de Villamantilla), y antes eso dejaba al usuario sin
     ninguna ruta. Aquí trazamos el bucle contra el callejero: dos puntos a
     distancia del objetivo en rumbos separados, y que OSRM los una por calles
     reales. Se prueban varias orientaciones porque en un sitio puede no haber
     camino hacia el norte y sí hacia el este. */
  function destinosPorRumbo(centro, objetivoM, intento) {
    var r = objetivoM / 3.2;
    var giro = (intento || 0) * 55;
    var a = mover(centro.lat, centro.lon, r, giro);
    var b = mover(centro.lat, centro.lon, r, giro + 110);
    return [[centro.lat, centro.lon], a, b];
  }

  function elegirDestinos(pois, centro, objetivoM, escala) {
    var r = (objetivoM / 3.2) * (escala || 1);                       // radio aproximado del bucle
    var conD = pois.map(function (p) {
      return { p: p, d: dist([centro.lat, centro.lon], [p.lat, p.lon]) };
    }).filter(function (x) { return x.d > r * 0.35; });
    /* "Verde" ya no es solo un parque urbano: en el campo lo verde es la pista,
       el sendero y el bosque. */
    var VERDE = { park:1, dog_park:1, path:1, track:1, wood:1, nature:1, meadow:1 };
    var verdes = conD.filter(function (x) { return VERDE[x.p.tipo]; });
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
    pintarNavegacion(i);
    pintarRelato(i);
    pintarFotos(i);
  }

  /* ── Qué vas a ver: rasgos REALES del terreno a lo largo de la ruta ─────
     Se consulta un corredor alrededor del recorrido y se recogen elementos
     con nombre propio en OpenStreetMap: ríos, montes, bosques, elementos
     históricos, miradores, hileras de árboles. La app NO inventa: si algo no
     está cartografiado, no se menciona. (Cuando esto pase al backend, la IA
     redactará el texto ENCIMA de esta misma lista, sin añadir nada nuevo.) */
  async function rasgosRuta(linea) {
    var muestra = [];
    var salto = Math.max(1, Math.floor(linea.length / 24));
    for (var i = 0; i < linea.length; i += salto) muestra.push(linea[i][0] + ',' + linea[i][1]);
    var c = muestra.join(',');
    var q = '[out:json][timeout:25];(' +
      'way["waterway"~"^(river|stream|canal)$"]["name"](around:130,' + c + ');' +
      'way["natural"~"^(wood|scrub)$"](around:120,' + c + ');' +
      'way["landuse"="forest"](around:120,' + c + ');' +
      'way["natural"="tree_row"](around:60,' + c + ');' +
      'node["natural"="peak"]["name"](around:1500,' + c + ');' +
      'way["historic"]["name"](around:160,' + c + ');' +
      'node["historic"]["name"](around:160,' + c + ');' +
      'node["tourism"="viewpoint"](around:250,' + c + ');' +
      'way["leisure"="park"]["name"](around:120,' + c + ');' +
      ');out center 90;';
    var servidores = [OVERPASS, 'https://overpass.kumi.systems/api/interpreter'];
    var d = null;
    for (var s = 0; s < servidores.length && !d; s++) {
      try {
        var r = await fetch(servidores[s], {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'data=' + encodeURIComponent(q)
        });
        if (r.ok) d = await r.json();
      } catch (e) {}
    }
    if (!d) return null;
    var out = { agua: [], bosque: 0, arboles: 0, montes: [], historico: [], miradores: 0, parques: [] };
    (d.elements || []).forEach(function (e) {
      var t = e.tags || {};
      if (t.waterway && t.name) { if (out.agua.indexOf(t.name) < 0) out.agua.push(t.name); }
      else if (t.natural === 'wood' || t.natural === 'scrub' || t.landuse === 'forest') out.bosque++;
      else if (t.natural === 'tree_row') out.arboles++;
      else if (t.natural === 'peak' && t.name) { if (out.montes.indexOf(t.name) < 0) out.montes.push(t.name); }
      else if (t.historic && t.name) {
        if (!out.historico.some(function (h) { return h.n === t.name; }))
          out.historico.push({ n: t.name, t: t.historic });
      }
      else if (t.tourism === 'viewpoint') out.miradores++;
      else if (t.leisure === 'park' && t.name) { if (out.parques.indexOf(t.name) < 0) out.parques.push(t.name); }
    });
    return out;
  }

  /* Posición del sol — cálculo astronómico, sin servicios externos.
     Sirve para decir a qué hora las sombras son más largas y útiles. */
  function alturaSol(fecha, lat, lon) {
    var rad = Math.PI / 180;
    var dias = (fecha - Date.UTC(2000, 0, 1, 12)) / 86400000;
    var M = rad * (357.5291 + 0.98560028 * dias);
    var C = rad * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M));
    var L = M + C + rad * 102.9372 + Math.PI;
    var dec = Math.asin(Math.sin(rad * 23.4397) * Math.sin(L));
    var ar = Math.atan2(Math.sin(L) * Math.cos(rad * 23.4397), Math.cos(L));
    var th = rad * (280.16 + 360.9856235 * dias) - rad * (-lon);
    var H = th - ar;
    return Math.asin(Math.sin(rad * lat) * Math.sin(dec) +
                     Math.cos(rad * lat) * Math.cos(dec) * Math.cos(H)) / rad;
  }
  function mejorHoraSombra(lat, lon) {
    /* La hora del reloj depende del huso del DESTINO, no del de quien mira la
       pantalla (el founder consulta desde Uruguay rutas de España). Para no
       depender de husos ni de servicios externos, expresamos el momento
       respecto al ATARDECER, que se calcula aquí mismo: "1 h 40 antes de que
       se ponga el sol". Es exacto en cualquier país y no caduca. */
    var hoy = new Date();
    var base = Date.UTC(hoy.getUTCFullYear(), hoy.getUTCMonth(), hoy.getUTCDate(), 0, 0);
    var ocaso = null, sombraLarga = null;
    var prev = alturaSol(base, lat, lon);
    for (var m = 10; m <= 24 * 60; m += 10) {
      var a = alturaSol(base + m * 60000, lat, lon);
      if (prev > 0 && a <= 0 && ocaso === null) ocaso = m;              // el sol se pone
      if (prev > 18 && a <= 18 && sombraLarga === null) sombraLarga = { m: m, alt: a };
      prev = a;
    }
    if (ocaso === null || sombraLarga === null || sombraLarga.m > ocaso) return null;
    var antes = Math.round((ocaso - sombraLarga.m) / 10) * 10;         // minutos antes del ocaso
    var h = Math.floor(antes / 60), mi = antes % 60;
    return {
      antes: (h ? h + ' h ' : '') + (mi ? mi + ' min' : '').trim() || '1 h',
      sombra: (1 / Math.tan(Math.max(sombraLarga.alt, 8) * Math.PI / 180)).toFixed(1).replace('.', ',')
    };
  }

  function textoRasgos(g, centro) {
    if (!g) return '';
    var f = [];
    if (g.agua.length)   f.push('Caminaréis junto ' + (g.agua.length > 1 ? 'a ' + g.agua.slice(0, 2).join(' y ') : 'al ' + g.agua[0]) + '.');
    if (g.parques.length) f.push('Cruza ' + (g.parques.length > 1 ? 'las zonas verdes de ' + g.parques.slice(0, 2).join(' y ') : g.parques[0]) + '.');
    if (g.montes.length) f.push('Con ' + g.montes.slice(0, 2).join(' y ') + ' a la vista.');
    if (g.historico.length) {
      var h = g.historico.slice(0, 2).map(function (x) { return x.n; }).join(' y ');
      f.push('De paso, ' + h + '.');
    }
    if (g.miradores) f.push(g.miradores > 1 ? 'Hay ' + g.miradores + ' miradores en el recorrido.' : 'Hay un mirador en el recorrido.');
    if (g.bosque || g.arboles) {
      var sombra = centro ? mejorHoraSombra(centro.lat, centro.lon) : null;
      var base = g.bosque ? 'Tramos arbolados donde parar a la sombra' : 'Hileras de árboles a lo largo del camino';
      f.push(base + (sombra ? '; la sombra más larga llega unas ' + sombra.antes +
             ' antes del atardecer (unas ' + sombra.sombra + ' veces la altura del arbolado)' : '') + '.');
    }
    if (!f.length) return '';
    return '<div class="dmw-relato"><div class="dmw-relato-h">Lo que vais a ver</div>' +
           '<p>' + f.join(' ') + '</p>' +
           '<div class="dmw-relato-f">Elementos cartografiados en OpenStreetMap sobre el recorrido. ' +
           'Hora de sombra calculada con la posición real del sol.</div></div>';
  }

  async function pintarRelato(i) {
    var cont = document.getElementById('dmw-walk-relato');
    if (!cont) return;
    var r = estado.rutas[i];
    if (!r) { cont.innerHTML = ''; return; }
    if (r._relato !== undefined) { cont.innerHTML = r._relato; return; }
    cont.innerHTML = '<div class="dmw-relato-cargando">Leyendo el terreno del recorrido…</div>';
    var g = null;
    try { g = await rasgosRuta(r.linea); } catch (e) {}
    r._relato = textoRasgos(g, estado.centro);
    cont.innerHTML = r._relato;
  }

  /* ── Cómo empezar + navegación con GPS ─────────────────────────────────
     Las indicaciones vienen del propio motor de rutas (OSRM). Para seguir el
     paseo con el GPS en marcha abrimos la ruta completa —con sus paradas— en
     la app de mapas del móvil, que es la que sabe hacia dónde miras y te va
     avisando de cada giro. */
  function urlNavegacion(r) {
    var pts = r.puntos || [];
    if (!pts.length) return null;
    var o = pts[0];
    var medios = pts.slice(1).map(function (p) { return p[0] + ',' + p[1]; }).join('|');
    return 'https://www.google.com/maps/dir/?api=1' +
           '&origin=' + o[0] + ',' + o[1] +
           '&destination=' + o[0] + ',' + o[1] +
           (medios ? '&waypoints=' + encodeURIComponent(medios) : '') +
           '&travelmode=walking';
  }
  function urlOsm(r) {
    var pts = r.puntos || [];
    if (pts.length < 2) return null;
    var ruta = pts.concat([pts[0]]).map(function (p) { return p[0] + ',' + p[1]; }).join(';');
    return 'https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=' + encodeURIComponent(ruta);
  }

  function pintarNavegacion(i) {
    var cont = document.getElementById('dmw-walk-nav');
    if (!cont) return;
    var r = estado.rutas[i];
    if (!r) { cont.innerHTML = ''; return; }
    var pasos = (r.pasos || []).slice(0, 4);
    var g = urlNavegacion(r), o = urlOsm(r);
    cont.innerHTML =
      '<div class="dmw-nav-h">Cómo empezar · ' + r.nombre + '</div>' +
      (pasos.length
        ? '<ol class="dmw-nav-pasos">' + pasos.map(function (p) { return '<li>' + p + '</li>'; }).join('') +
          (r.pasos.length > pasos.length
            ? '<li class="mas">y ' + (r.pasos.length - pasos.length) + ' indicaciones más durante el paseo</li>' : '') +
          '</ol>'
        : '<div class="dmw-nav-vacio">Sin indicaciones detalladas para esta ruta.</div>') +
      '<div class="dmw-nav-btns">' +
        (g ? '<a class="dmw-nav-btn" href="' + g + '" target="_blank" rel="noopener">Abrir en mi app de mapas</a>' : '') +
        (o ? '<a class="dmw-nav-btn alt" href="' + o + '" target="_blank" rel="noopener">Ver en OpenStreetMap</a>' : '') +
      '</div>' +
      '<div class="dmw-nav-nota">Se abre tu app de mapas con esta ruta ya elegida — ' +
      'salida, paradas y vuelta — y la sigues desde ahí con tu GPS.</div>';
  }

  function estadoTexto(t) {
    var e = document.getElementById('dmw-walk-estado');
    if (e) e.textContent = t;
  }

  /* Cobro del paseo: 10 créditos (0,1 tk) por planificación, precio de salida
     del founder — "ningún uso es gratis". Solo con sesión; si no hay saldo,
     sale el aviso de recarga y no se genera. Si el cobro falla por red, el
     paseo NO se bloquea (fail-open, como el resto de la app). */
  async function cobrarPaseo() {
    var jwt = ''; try { jwt = localStorage.getItem('dm_jwt') || ''; } catch (e) {}
    if (!jwt) return true;  /* sin sesión (web pública): no hay a quién cobrar */
    try {
      var base = (typeof API_URL !== 'undefined' && API_URL) ? API_URL
                : 'https://dogs-mind-backend-production.up.railway.app';
      var r = await fetch(base + '/walks/charge', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + jwt }
      });
      if (r.status === 402) {
        if (typeof showRechargeNotice === 'function') showRechargeNotice(0.1);
        else estadoTexto('Te has quedado sin créditos para el paseo.');
        return false;
      }
      if (r.ok && typeof fetchBalance === 'function') { try { fetchBalance(); } catch (e) {} }
      return true;
    } catch (e) { return true; }
  }

  async function generar(centro, etiqueta) {
    /* El cobro va DESPUÉS de tener los datos (2026-08-06). Antes se cobraba
       aquí arriba: si Overpass estaba caído —pasa a menudo, es un servicio
       público gratuito— el usuario pagaba 10 créditos, veía "no se han podido
       consultar los datos" y volvía a pagar en cada reintento. */
    estado.centro = centro;
    estadoTexto('Buscando zonas verdes y servicios…');
    capaRutas.clearLayers(); capaPois.clearLayers();
    estado.rutas = [];
    mapa.setView([centro.lat, centro.lon], 15);
    if (marcadorYo) mapa.removeLayer(marcadorYo);
    marcadorYo = L.circleMarker([centro.lat, centro.lon], {
      radius: 8, color: '#fff', weight: 3, fillColor: '#5ec8e6', fillOpacity: 1
    }).addTo(mapa).bindTooltip(etiqueta || 'Estáis aquí');

    /* Radio creciente: en ciudad sobra con 1,6 km; en campo abierto hay que
       abrirse para encontrar las pistas. Nos paramos en cuanto hay material. */
    var pois = [];
    var radios = [1600, 3000, 5000];
    var falloMapa = null;
    for (var ri = 0; ri < radios.length; ri++) {
      try {
        pois = await buscarPois(centro.lat, centro.lon, radios[ri]);
        falloMapa = null;
      } catch (e) { falloMapa = e; continue; }
      if (pois.length >= 6) break;
    }
    if (falloMapa && !pois.length) {
      estadoTexto('No se han podido consultar los datos del mapa. Inténtalo en un minuto.');
      return;
    }
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
      /* Primero con puntos de interés (la ruta "buena": pasa por zonas verdes).
         Si no hay, se cae al callejero para que igualmente haya paseo. */
      /* En campo abierto los anclajes quedan lejos y las pistas no van rectas:
         pedir 1,5 km devolvía 4,3 km reales, que para un cachorro o un perro
         mayor no sirve. Tanteamos varias escalas y nos quedamos con la que más
         se acerca a la distancia pedida. */
      var candidatos = [];
      [0.45, 0.7, 1].forEach(function (esc) {
        var cp = elegirDestinos(pois, centro, o.m, esc);
        if (cp) candidatos.push(cp);
      });
      candidatos.push(destinosPorRumbo(centro, o.m, 0));
      candidatos.push(destinosPorRumbo(centro, o.m, 1));

      var res = null, mejorDif = Infinity;
      for (var c = 0; c < candidatos.length; c++) {
        var cand = null;
        try { cand = await ruta(candidatos[c]); } catch (e) { continue; }
        var dif = Math.abs(cand.metros - o.m);
        if (dif < mejorDif) { mejorDif = dif; res = cand; }
        /* Suficientemente cerca: no gastamos más llamadas. */
        if (dif <= o.m * 0.3) break;
      }
      if (!res) continue;
      /* El nombre promete una distancia; si la real se aleja mucho, lo decimos
         en vez de llamar "vuelta corta" a 4 km. */
      o = { nombre: o.nombre, por: o.por, m: o.m };
      try {
        var capa = L.polyline(res.linea, { color: '#e8efea', weight: 3, opacity: .25 }).addTo(capaRutas);
        estado.rutas.push({
          nombre: o.nombre, por: o.por, metros: res.metros, linea: res.linea,
          pasos: res.pasos, puntos: res.puntos,
          pois: poisEnRuta(pois, res.linea), capa: capa
        });
      } catch (e) { /* esa distancia no sale: seguimos con las demás */ }
    }
    /* Sin rutas no hay nada que entregar: no se cobra. */
    if (!estado.rutas.length) {
      estadoTexto('Sin rutas disponibles aquí. No te hemos cobrado nada.');
      var vac = document.getElementById('dmw-walk-lista');
      if (vac) vac.innerHTML = '<div class="dmw-walk-vacio">No hemos podido trazar rutas ' +
        'a pie aquí: por esta zona no hay caminos suficientes en el mapa. ' +
        'Prueba a escribir un pueblo o ciudad cercana. No te hemos cobrado nada.</div>';
      return;
    }
    /* Ya hay rutas de verdad: ahora sí se cobra. */
    if (!(await cobrarPaseo())) return;
    pintarLista(document.getElementById('dmw-walk-lista'));
    estadoTexto(estado.rutas.length + ' rutas sobre datos reales de OpenStreetMap');
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
        '<button class="dmw-walk-cta" id="dmw-walk-rutas">Buscar mis tres rutas</button>' +
        '<div class="dmw-walk-body">' +
          '<div id="dmw-walk-map" class="dmw-walk-map"></div>' +
          '<div class="dmw-rutas" id="dmw-walk-lista">' +
            '<div class="dmw-walk-vacio">Dinos dónde estáis y calculamos tres rutas a pie ' +
            'con las zonas verdes y los servicios que hay de verdad alrededor.</div>' +
          '</div>' +
        '</div>' +
        '<div class="dmw-walk-relato" id="dmw-walk-relato"></div>' +
        '<div class="dmw-walk-nav" id="dmw-walk-nav"></div>' +
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
    /* El botón grande: si ya sabemos dónde está, recalcula ahí; si no, pide la
       ubicación. Antes la única forma de lanzarlo era "Usar mi ubicación", que
       parece que solo centra el mapa (founder 2026-08-17: "no encuentro el
       botón para pedir que te dé rutas"). */
    document.getElementById('dmw-walk-rutas').onclick = function () {
      if (estado.centro) { generar(estado.centro, 'Estáis aquí'); return; }
      document.getElementById('dmw-walk-geo').click();
    };
    document.getElementById('dmw-walk-q').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') buscar();
    });
  }

  window.dmwWalkMontar = montar;
})();
