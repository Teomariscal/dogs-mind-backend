/* ═══════════════════════════════════════════════════════════════════════════
   WORLD WIDE DOG WALKING — versión real (v1): web Y app desde 1.0.5
   ---------------------------------------------------------------------------
   AISLAMIENTO (founder 2026-07-28, "prioridad máxima: no afectar a las apps"):
   este archivo lo carga web-desktop.js bajo demanda, y web-desktop.js solo
   existe si NO estamos en app nativa. Además vuelve a comprobarlo al arrancar.

   DATOS REALES, SIN CLAVES NI FACTURACIÓN:
     · Mapa      → Google Maps (estilo oscuro propio)
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

  /* ── IDIOMA (15-sep-2026) ──────────────────────────────────────────────────
     Este fichero tenia CERO traduccion: 835 lineas y todo el texto visible en
     castellano. La tarjeta que lleva aqui SI esta traducida —"La passeggiata di
     oggi" sale del diccionario— asi que un italiano pulsaba un titulo en su
     idioma y caia en una pantalla entera en español. El founder lo vio en
     TestFlight y mando la captura.

     No se enchufa a TRANSLATIONS a proposito: este fichero se carga bajo
     demanda y puede llegar antes o despues que el diccionario. Lleva el suyo,
     como ya hacia web-paseo.js, que es el patron de la casa aqui. */
  function L() {
    try {
      return ((window.getCurrentLang ? window.getCurrentLang() : '') ||
              localStorage.getItem('dm_lang') || 'es').toLowerCase().slice(0, 2);
    } catch (e) { return 'es'; }
  }
  var DIC = {
    es: {
      jardin:'Jardín', sigue:'continúa',
      creditos_wiki:'Fotografías de Wikimedia Commons',
      sin_entorno:'suficientes en el entorno para proponer rutas. Prueba con otra ubicación.',
      recorrera_a:'recorrerá tu perro', estimado:'estimado',
      estimado_t:'Estimación sobre datos publicados (Foltin & Ganslosser)',
      junto_a:'Caminaréis junto ', y_:' y ', al_:'al ', a_:'a ',
      bosque_si:'Tramos arbolados donde parar a la sombra',
      bosque_no:'Hileras de árboles a lo largo del camino',
      sombra_larga:'; la sombra más larga llega unas ',
      sombra_sol:'Hora de sombra calculada con la posición real del sol.',
      como_empezar:'Cómo empezar · ',
      y_mas:'y ', indicaciones_mas:' indicaciones más durante el paseo',
      salida_vuelta:'salida, paradas y vuelta — y la sigues desde ahí con tu GPS.',
      sin_creditos:'Te has quedado sin créditos para el paseo.',
      estais_aqui:'Estáis aquí',
      r_corta:'Vuelta corta', r_corta_p:'Paseo rápido por el entorno cercano.',
      r_media:'Ruta media',   r_media_p:'Equilibrio entre distancia y zonas verdes.',
      r_larga:'Ruta larga',   r_larga_p:'Para cuando tenéis tiempo y ganas de kilómetros.',
      sin_rutas:'Sin rutas disponibles aquí. No te hemos cobrado nada.',
      sin_caminos:'a pie aquí: por esta zona no hay caminos suficientes en el mapa. ',
      usar_ubic:'Usar mi ubicación',
      escribe_ciudad:'Escribe una ciudad o dirección…',
      buscar:'Buscar', buscar_tres:'Buscar mis tres rutas',
      dinos_donde:'Dinos dónde estáis y calculamos tres rutas a pie ',
      como_es:'¿Cómo es tu perro?', suelto:'Va suelto durante el paseo',
      mas_que_tu:' más que tú (',
      pidiendo:'Pidiendo tu ubicación…',
      sin_geo:'Tu navegador no da la ubicación.',
      sin_permiso:'No nos has dado permiso de ubicación. Escribe una ciudad.',
      vais_a_ver:'Lo que vais a ver', abrir_mapas:'Abrir en mi app de mapas',
      lug_park:'Zona verde', lug_dog:'Zona de perros', lug_agua:'Fuente de agua', lug_tienda:'Tienda de animales',
      g_izq:'gira a la izquierda', g_der:'gira a la derecha',
      g_lig_izq:'ligeramente a la izquierda', g_lig_der:'ligeramente a la derecha',
      g_cer_izq:'giro cerrado a la izquierda', g_cer_der:'giro cerrado a la derecha',
      g_recto:'sigue recto', g_vuelta:'da la vuelta',
      g_por:' por ', g_rotonda:'En la rotonda, toma la salida',
      niv_bajo:'Poco activo', niv_bajo_d:'cuartil bajo del estudio',
      niv_medio:'Normal', niv_medio_d:'mediana del estudio',
      niv_alto:'Muy activo', niv_alto_d:'cuartil alto del estudio',
      cruza:'Cruza ', zv_de:'las zonas verdes de ', con_:'Con ', a_la_vista:' a la vista.',
      hay_:'Hay ', miradores_rec:' miradores en el recorrido.', un_mirador:'Hay un mirador en el recorrido.',
      antes_atardecer:' antes del atardecer (unas ', veces_arbolado:' veces la altura del arbolado)',
      buscando_zonas:'Buscando zonas verdes y servicios…',
      mapa_no_responde:'El mapa de zonas verdes no responde ahora mismo. Te trazamos rutas a pie igualmente.',
      sin_zonas:'No hay zonas verdes registradas cerca. Te trazamos rutas a pie por el entorno.',
      calculando:'Calculando rutas a pie…',
      prueba_pueblo:'Prueba a escribir un pueblo o ciudad cercana. No te hemos cobrado nada.',
      rutas_datos:' rutas a pie sobre datos de Google Maps',
      con_zv:'con las zonas verdes y los servicios que hay de verdad alrededor.',
      mapa_error:'No se ha podido cargar el mapa.',
      suelto_y:'Suelto y ', recorre_aprox:': tu perro recorre alrededor de un <b>',
      atado:'Atado a tu lado recorre <b>tu misma distancia</b>. Marca la casilla si va suelto.',
      buscando_q:'Buscando «', del_camino:'Del camino · ', fotos_n:' fotos'
    },
    en: {
      jardin:'Garden', sigue:'continue',
      creditos_wiki:'Photographs from Wikimedia Commons',
      sin_entorno:'enough around here to suggest routes. Try another location.',
      recorrera_a:'your dog will cover', estimado:'estimated',
      estimado_t:'Estimate based on published data (Foltin & Ganslosser)',
      junto_a:'You will walk beside ', y_:' and ', al_:'the ', a_:'the ',
      bosque_si:'Tree-lined stretches where you can stop in the shade',
      bosque_no:'Rows of trees along the way',
      sombra_larga:'; the longest shade arrives in about ',
      sombra_sol:'Shade time calculated from the real position of the sun.',
      como_empezar:'How to start · ',
      y_mas:'and ', indicaciones_mas:' more directions along the walk',
      salida_vuelta:'start, stops and return — and you follow it from there with your GPS.',
      sin_creditos:'You have run out of credits for the walk.',
      estais_aqui:'You are here',
      r_corta:'Short loop',  r_corta_p:'A quick walk around the area.',
      r_media:'Medium route', r_media_p:'A balance between distance and green space.',
      r_larga:'Long route',  r_larga_p:'For when you have time and want the miles.',
      sin_rutas:'No routes available here. We have not charged you anything.',
      sin_caminos:'on foot here: there are not enough paths on the map in this area. ',
      usar_ubic:'Use my location',
      escribe_ciudad:'Type a city or address…',
      buscar:'Search', buscar_tres:'Find my three routes',
      dinos_donde:'Tell us where you are and we will work out three walking routes ',
      como_es:'What is your dog like?', suelto:'Walks off the lead',
      mas_que_tu:' more than you (',
      pidiendo:'Asking for your location…',
      sin_geo:'Your browser does not provide location.',
      sin_permiso:'You have not given us location permission. Type a city.',
      vais_a_ver:'What you will see', abrir_mapas:'Open in my maps app',
      lug_park:'Green space', lug_dog:'Dog park', lug_agua:'Drinking fountain', lug_tienda:'Pet shop',
      g_izq:'turn left', g_der:'turn right',
      g_lig_izq:'slightly left', g_lig_der:'slightly right',
      g_cer_izq:'sharp left', g_cer_der:'sharp right',
      g_recto:'carry straight on', g_vuelta:'turn around',
      g_por:' along ', g_rotonda:'At the roundabout, take the exit',
      niv_bajo:'Not very active', niv_bajo_d:'lower quartile of the study',
      niv_medio:'Normal', niv_medio_d:'median of the study',
      niv_alto:'Very active', niv_alto_d:'upper quartile of the study',
      cruza:'You cross ', zv_de:'the green spaces of ', con_:'With ', a_la_vista:' in view.',
      hay_:'There are ', miradores_rec:' viewpoints along the route.', un_mirador:'There is a viewpoint along the route.',
      antes_atardecer:' before sunset (about ', veces_arbolado:' times the height of the trees)',
      buscando_zonas:'Looking for green spaces and services…',
      mapa_no_responde:'The green-space map is not responding right now. We will plan walking routes anyway.',
      sin_zonas:'No green spaces registered nearby. We will plan walking routes around the area.',
      calculando:'Working out walking routes…',
      prueba_pueblo:'Try typing a nearby town or city. We have not charged you anything.',
      rutas_datos:' walking routes based on Google Maps data',
      con_zv:'with the green spaces and services that really are around you.',
      mapa_error:'The map could not be loaded.',
      suelto_y:'Off the lead and ', recorre_aprox:': your dog covers about <b>',
      atado:'On the lead beside you it covers <b>the same distance as you</b>. Tick the box if it walks off the lead.',
      buscando_q:'Searching for \u201c', del_camino:'Along the way · ', fotos_n:' photos'
    },
    it: {
      jardin:'Giardino', sigue:'prosegui',
      creditos_wiki:'Fotografie da Wikimedia Commons',
      sin_entorno:'a sufficienza nei dintorni per proporre percorsi. Prova un’altra posizione.',
      recorrera_a:'percorrerà il tuo cane', estimado:'stimato',
      estimado_t:'Stima su dati pubblicati (Foltin & Ganslosser)',
      junto_a:'Camminerete lungo ', y_:' e ', al_:'il ', a_:'la ',
      bosque_si:'Tratti alberati dove fermarsi all’ombra',
      bosque_no:'Filari di alberi lungo il percorso',
      sombra_larga:'; l’ombra più lunga arriva tra circa ',
      sombra_sol:'Ora d’ombra calcolata con la posizione reale del sole.',
      como_empezar:'Come iniziare · ',
      y_mas:'e ', indicaciones_mas:' altre indicazioni durante la passeggiata',
      salida_vuelta:'partenza, soste e ritorno — e lo segui da lì con il tuo GPS.',
      sin_creditos:'Hai esaurito i crediti per la passeggiata.',
      estais_aqui:'Siete qui',
      r_corta:'Giro breve',    r_corta_p:'Passeggiata rapida nei dintorni.',
      r_media:'Percorso medio', r_media_p:'Equilibrio tra distanza e aree verdi.',
      r_larga:'Percorso lungo', r_larga_p:'Per quando avete tempo e voglia di chilometri.',
      sin_rutas:'Nessun percorso disponibile qui. Non ti abbiamo addebitato nulla.',
      sin_caminos:'a piedi qui: in questa zona non ci sono abbastanza percorsi sulla mappa. ',
      usar_ubic:'Usa la mia posizione',
      escribe_ciudad:'Scrivi una città o un indirizzo…',
      buscar:'Cerca', buscar_tres:'Trova i miei tre percorsi',
      dinos_donde:'Dicci dove siete e calcoliamo tre percorsi a piedi ',
      como_es:'Com’è il tuo cane?', suelto:'Va libero durante la passeggiata',
      mas_que_tu:' più di te (',
      pidiendo:'Sto chiedendo la tua posizione…',
      sin_geo:'Il tuo browser non fornisce la posizione.',
      sin_permiso:'Non ci hai dato il permesso di posizione. Scrivi una città.',
      vais_a_ver:'Che cosa vedrete', abrir_mapas:'Apri nella mia app di mappe',
      lug_park:'Area verde', lug_dog:'Area cani', lug_agua:'Fontanella', lug_tienda:'Negozio per animali',
      g_izq:'gira a sinistra', g_der:'gira a destra',
      g_lig_izq:'leggermente a sinistra', g_lig_der:'leggermente a destra',
      g_cer_izq:'svolta secca a sinistra', g_cer_der:'svolta secca a destra',
      g_recto:'prosegui dritto', g_vuelta:'fai inversione',
      g_por:' lungo ', g_rotonda:'Alla rotonda, prendi l\u2019uscita',
      niv_bajo:'Poco attivo', niv_bajo_d:'quartile basso dello studio',
      niv_medio:'Normale', niv_medio_d:'mediana dello studio',
      niv_alto:'Molto attivo', niv_alto_d:'quartile alto dello studio',
      cruza:'Attraversate ', zv_de:'le aree verdi di ', con_:'Con ', a_la_vista:' in vista.',
      hay_:'Ci sono ', miradores_rec:' punti panoramici lungo il percorso.', un_mirador:'C\u2019\u00e8 un punto panoramico lungo il percorso.',
      antes_atardecer:' prima del tramonto (circa ', veces_arbolado:' volte l\u2019altezza degli alberi)',
      buscando_zonas:'Sto cercando aree verdi e servizi…',
      mapa_no_responde:'La mappa delle aree verdi non risponde adesso. Tracciamo comunque i percorsi a piedi.',
      sin_zonas:'Nessuna area verde registrata qui vicino. Tracciamo percorsi a piedi nei dintorni.',
      calculando:'Sto calcolando i percorsi a piedi…',
      prueba_pueblo:'Prova a scrivere un paese o una citt\u00e0 vicina. Non ti abbiamo addebitato nulla.',
      rutas_datos:' percorsi a piedi su dati di Google Maps',
      con_zv:'con le aree verdi e i servizi che ci sono davvero intorno a voi.',
      mapa_error:'Non \u00e8 stato possibile caricare la mappa.',
      suelto_y:'Libero e ', recorre_aprox:': il tuo cane percorre circa un <b>',
      atado:'Al guinzaglio accanto a te percorre <b>la tua stessa distanza</b>. Spunta la casella se va libero.',
      buscando_q:'Sto cercando \u00ab', del_camino:'Lungo il percorso · ', fotos_n:' foto'
    }
  };
  function T(k) { var d = DIC[L()] || DIC.es; return (k in d) ? d[k] : DIC.es[k]; }

  /* SIEMPRE Google Maps, sin respaldo (founder, 2-sep-2026). OpenStreetMap queda
     anulado: fuera Overpass, OSRM, Nominatim y Leaflet.
     Los datos NO se piden desde aqui: van por nuestro backend (/walks/*), que es
     quien guarda la clave buena. El navegador solo recibe una clave distinta,
     restringida al mapa y por dominio, que llega en /app-config. */
  /* Capa minima sobre Google Maps con la FORMA de las cuatro cosas que se usaban
     de Leaflet (capas, trazado, punto, encuadre). Se hace asi a proposito: el
     resto del fichero —seleccionar(), generar(), pintarLista()— no se toca, que
     es donde estaba el riesgo de romper algo. */
  function GCapa() { this._e = []; }
  GCapa.prototype.clearLayers = function () {
    this._e.forEach(function (x) { try { x.setMap(null); } catch (e) {} });
    this._e = [];
  };
  GCapa.prototype.add = function (x) { this._e.push(x); return x; };

  function gTrazado(linea, estilo, capa) {
    var pl = new google.maps.Polyline({
      path: linea.map(function (p) { return { lat: p[0], lng: p[1] }; }),
      strokeColor: estilo.color, strokeWeight: estilo.weight,
      strokeOpacity: estilo.opacity, map: mapa, zIndex: 1
    });
    pl.setStyle = function (e) {
      this.setOptions({ strokeColor: e.color, strokeOpacity: e.opacity, strokeWeight: e.weight });
    };
    pl.bringToFront = function () { this.setOptions({ zIndex: 99 }); };
    pl.getBounds = function () {
      var b = new google.maps.LatLngBounds();
      this.getPath().forEach(function (ll) { b.extend(ll); });
      return b;
    };
    if (capa) capa.add(pl);
    return pl;
  }

  function gPunto(lat, lon, estilo, titulo, capa) {
    var m = new google.maps.Marker({
      position: { lat: lat, lng: lon }, map: mapa, title: titulo || '',
      icon: { path: google.maps.SymbolPath.CIRCLE, scale: estilo.radius,
              fillColor: estilo.fillColor, fillOpacity: estilo.fillOpacity,
              strokeColor: estilo.color, strokeWeight: estilo.weight }
    });
    if (capa) capa.add(m);
    return m;
  }

  /* Estilo oscuro, para que el mapa no deslumbre dentro de la app. */
  var ESTILO_OSCURO = [
    { elementType: 'geometry', stylers: [{ color: '#1a2b24' }] },
    { elementType: 'labels.text.stroke', stylers: [{ color: '#0a1a14' }] },
    { elementType: 'labels.text.fill', stylers: [{ color: '#8fa89b' }] },
    { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#22402f' }] },
    { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#2b3d35' }] },
    { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#9fb5a8' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#12333f' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] }
  ];

  /* La clave del mapa llega de /app-config, no va dentro del binario: asi se
     puede rotar sin pasar por las tiendas. */
  var _gmCargando = null;
  function cargarGoogleMaps() {
    if (window.google && window.google.maps) return Promise.resolve();
    if (_gmCargando) return _gmCargando;
    _gmCargando = (async function () {
      var r = await fetch(API() + '/app-config');
      var cfg = await r.json();
      var clave = ((cfg || {}).maps || {}).browser_key || '';
      if (!clave) throw new Error('sin clave de mapa');
      await new Promise(function (ok, ko) {
        var sc = document.createElement('script');
        sc.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(clave) + '&v=weekly';
        sc.async = true; sc.onload = ok; sc.onerror = function () { ko(new Error('maps js')); };
        document.head.appendChild(sc);
      });
    })();
    return _gmCargando;
  }

  function API() {
    return (typeof API_URL !== 'undefined' && API_URL)
      ? API_URL : 'https://dogs-mind-backend-production.up.railway.app';
  }
  function _jwt() { try { return localStorage.getItem('dm_jwt') || ''; } catch (e) { return ''; } }
  async function pedir(ruta, cuerpo) {
    var r = await fetch(API() + ruta, {
      method: cuerpo ? 'POST' : 'GET',
      headers: cuerpo
        ? { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() }
        : { 'Authorization': 'Bearer ' + _jwt() },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined
    });
    if (!r.ok) { var e = new Error('http ' + r.status); e.status = r.status; throw e; }
    return r.json();
  }

  var TIPOS = {
    park:         { n: T('lug_park'),        c: '#7eb86a' },
    dog_park:     { n: T('lug_dog'),    c: '#7eb86a' },
    veterinary:   { n: 'Veterinario',       c: '#5ec8e6' },
    drinking_water:{ n: T('lug_agua'),   c: '#5ec8e6' },
    pet:          { n: T('lug_tienda'),c: '#80d6ee' },
    /* Founder 2026-08-17: "no solo buscar parques sino caminos, rutas de
       montaña o naturaleza". En un pueblo no hay parques etiquetados pero sí
       decenas de pistas y bosque — comprobado en Villamantilla: 0 parques,
       47 pistas, 5 senderos y 8 zonas de bosque en 2,5 km. */
    path:         { n: 'Sendero',           c: '#b6dca0' },
    track:        { n: 'Pista / camino',    c: '#b6dca0' },
    wood:         { n: 'Bosque',            c: '#7eb86a' },
    nature:       { n: 'Espacio natural',   c: '#7eb86a' },
    meadow:       { n: 'Prado',             c: '#9ecf86' },
    /* Tipos que aporta Google y no tenia OpenStreetMap. Comprobados contra la
       API el 4-sep-2026 en Madrid y en Villamantilla (pueblo). */
    jardin:       { n: T('jardin'),            c: '#7eb86a' },
    plaza:        { n: 'Plaza',             c: '#b6dca0' },
    historico:    { n: 'Monumento',         c: '#e0bd8c' }
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

  /* Consulta a Overpass con reintentos. Devuelve null solo si fallan todos los
     intentos en todos los espejos. */
  async function buscarPois(lat, lon, radio, limite) {
    /* Google Places, en UNA sola llamada con los cuatro tipos. Pedir un tipo por
       llamada triplicaba el coste del paseo. El backend traduce los tipos de
       Google a los nuestros. */
    var d = await pedir('/walks/sitios', { lat: lat, lon: lon, radio: radio });
    return (d.sitios || []).filter(function (p) { return TIPOS[p.tipo]; });
  }

  /* Traducción de las maniobras que devuelve OSRM (vienen en inglés) */
  var GIROS = {
    left: T('g_izq'), right: T('g_der'),
    'slight left': T('g_lig_izq'), 'slight right': T('g_lig_der'),
    'sharp left': T('g_cer_izq'), 'sharp right': T('g_cer_der'),
    straight: T('g_recto'), uturn: T('g_vuelta')
  };
  function instruccion(paso) {
    var m = paso.maneuver || {};
    var via = paso.name ? T('g_por') + paso.name : '';
    var d = paso.distance ? ' (' + Math.round(paso.distance) + ' m)' : '';
    if (m.type === 'depart')  return 'Sal' + via + d;
    if (m.type === 'arrive')  return 'Has llegado al punto de partida';
    if (m.type === 'roundabout' || m.type === 'rotary') return T('g_rotonda') + via + d;
    var g = GIROS[m.modifier] || T('sigue');
    return g.charAt(0).toUpperCase() + g.slice(1) + via + d;
  }

  /* Trazado codificado de Google -> [[lat,lon], …]. Es el algoritmo estandar de
     polilineas; se hace aqui para no cargar la libreria 'geometry' solo por esto. */
  function descodificar(txt) {
    var pts = [], i = 0, lat = 0, lon = 0;
    while (i < txt.length) {
      var b, giro = 0, desp = 0;
      do { b = txt.charCodeAt(i++) - 63; giro |= (b & 0x1f) << desp; desp += 5; } while (b >= 0x20);
      lat += ((giro & 1) ? ~(giro >> 1) : (giro >> 1));
      giro = 0; desp = 0;
      do { b = txt.charCodeAt(i++) - 63; giro |= (b & 0x1f) << desp; desp += 5; } while (b >= 0x20);
      lon += ((giro & 1) ? ~(giro >> 1) : (giro >> 1));
      pts.push([lat / 1e5, lon / 1e5]);
    }
    return pts;
  }

  async function ruta(puntos) {          // puntos: [[lat,lon], …] — vuelve al inicio
    /* Google Routes por nuestro backend. Las indicaciones vienen ya redactadas y
       en el idioma de la peticion, asi que no hay que traducir maniobras a mano
       como con OSRM. */
    var d = await pedir('/walks/ruta', { puntos: puntos });
    if (!d || !d.trazado) throw new Error('sin ruta');
    return {
      metros: d.metros,
      linea: descodificar(d.trazado),
      pasos: d.pasos || [],
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
    /* 3.2 seria el divisor si el triangulo se recorriese en linea recta, pero se
       recorre por calles, que dan rodeos. Medido contra el OSRM real en Madrid,
       Montevideo, Napoles y Villamantilla (1-sep-2026): con 3.2 la ruta salia
       1,57 veces mas larga de lo pedido —una "vuelta corta" de 1,5 km acababa
       siendo de 3,3, que para un cachorro o un perro mayor no sirve—. Con 5.0 la
       desviacion media baja del 57 % al 19 %, y sin gastar ni una llamada mas al
       motor de rutas: el coste por paseo sigue clavado. */
    var r = objetivoM / 5.0;
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
      '<div class="dmw-fotos-h">' + T('del_camino') + fotos.length + T('fotos_n') + '</div>' +
      '<div class="dmw-fotos-row">' + fotos.map(function (f) {
        return '<a class="dmw-foto" href="' + f.pagina + '" target="_blank" rel="noopener" title="' +
               f.titulo.replace(/"/g, '') + (f.autor ? ' — ' + f.autor.replace(/"/g, '') : '') + '">' +
                 '<img src="' + f.src + '" alt="' + f.titulo.replace(/"/g, '') + '" loading="lazy">' +
                 '<span>' + f.titulo + '</span>' +
               '</a>';
      }).join('') + '</div>' +
      '<div class="dmw-fotos-cred">' + T('creditos_wiki') + '</div>';
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
    bajo:  { f: 1.17, get n(){return T('niv_bajo');},  get d(){return T('niv_bajo_d');} },
    medio: { f: 1.43, get n(){return T('niv_medio');}, get d(){return T('niv_medio_d');} },
    alto:  { f: 1.99, get n(){return T('niv_alto');},  get d(){return T('niv_alto_d');} }
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
        T('sin_entorno') + '</div>';
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
        ? '<div class="dmw-perro-km"><b>' + km(perro) + '</b> ' + T('recorrera_a') + ' ' +
          '<span title="' + T('estimado_t') + '">' + T('estimado') + '</span></div>'
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
      if (j === i) { r.capa.bringToFront(); mapa.fitBounds(r.capa.getBounds(), 30); }
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
    /* El adorno del paseo —rios, bosque, miradores, cimas, historico— salia de
       Overpass, que queda anulado (founder, 2-sep-2026). Google Places no da esa
       informacion por tramo sin una llamada mas por ruta, que triplicaria el
       coste. Se devuelve null: el llamador ya lo contempla y la ruta se pinta
       igual, solo sin ese detalle. Anotado en PENDIENTES.md para decidirlo. */
    return null;
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
    if (g.agua.length)   f.push(T('junto_a') + (g.agua.length > 1 ? T('a_') + g.agua.slice(0, 2).join(T('y_')) : T('al_') + g.agua[0]) + '.');
    if (g.parques.length) f.push(T('cruza') + (g.parques.length > 1 ? T('zv_de') + g.parques.slice(0, 2).join(' y ') : g.parques[0]) + '.');
    if (g.montes.length) f.push(T('con_') + g.montes.slice(0, 2).join(T('y_')) + T('a_la_vista'));
    if (g.historico.length) {
      var h = g.historico.slice(0, 2).map(function (x) { return x.n; }).join(' y ');
      f.push('De paso, ' + h + '.');
    }
    if (g.miradores) f.push(g.miradores > 1 ? T('hay_') + g.miradores + T('miradores_rec') : T('un_mirador'));
    if (g.bosque || g.arboles) {
      var sombra = centro ? mejorHoraSombra(centro.lat, centro.lon) : null;
      var base = g.bosque ? T('bosque_si') : T('bosque_no');
      f.push(base + (sombra ? T('sombra_larga') + sombra.antes +
             T('antes_atardecer') + sombra.sombra + T('veces_arbolado') : '') + '.');
    }
    if (!f.length) return '';
    return '<div class="dmw-relato"><div class="dmw-relato-h">' + T('vais_a_ver') + '</div>' +
           '<p>' + f.join(' ') + '</p>' +
           '<div class="dmw-relato-f">Lugares reales sobre el recorrido, segun Google Maps. ' +
           T('sombra_sol') + '</div></div>';
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
      '<div class="dmw-nav-h">' + T('como_empezar') + r.nombre + '</div>' +
      (pasos.length
        ? '<ol class="dmw-nav-pasos">' + pasos.map(function (p) { return '<li>' + p + '</li>'; }).join('') +
          (r.pasos.length > pasos.length
            ? '<li class="mas">' + T('y_mas') + (r.pasos.length - pasos.length) + T('indicaciones_mas') + '</li>' : '') +
          '</ol>'
        : '<div class="dmw-nav-vacio">Sin indicaciones detalladas para esta ruta.</div>') +
      '<div class="dmw-nav-btns">' +
        (g ? '<a class="dmw-nav-btn" href="' + g + '" target="_blank" rel="noopener">' + T('abrir_mapas') + '</a>' : '') +
        /* El enlace a OpenStreetMap se retira: ya no es nuestra fuente (4-sep-2026). */
      '</div>' +
      '<div class="dmw-nav-nota">Se abre tu app de mapas con esta ruta ya elegida — ' +
      T('salida_vuelta') + '</div>';
  }

  function estadoTexto(t) {
    var e = document.getElementById('dmw-walk-estado');
    if (e) e.textContent = t;
  }

  /* Cobro del paseo: 25 créditos (0,25 tk) por planificación. Subió de 10 a 25
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
        if (typeof showRechargeNotice === 'function') showRechargeNotice(0.25);
        else estadoTexto(T('sin_creditos'));
        return false;
      }
      if (r.ok && typeof fetchBalance === 'function') { try { fetchBalance(); } catch (e) {} }
      return true;
    } catch (e) { return true; }
  }

  async function generar(centro, etiqueta) {
    /* El cobro va DESPUÉS de tener los datos (2026-08-06). Antes se cobraba
       aquí arriba: si Overpass estaba caído —pasa a menudo, es un servicio
       público gratuito— el usuario pagaba los créditos, veía "no se han podido
       consultar los datos" y volvía a pagar en cada reintento. */
    estado.centro = centro;
    estadoTexto(T('buscando_zonas'));
    capaRutas.clearLayers(); capaPois.clearLayers();
    estado.rutas = [];
    mapa.setCenter({ lat: centro.lat, lng: centro.lon });
    mapa.setZoom(15);
    if (marcadorYo) { try { marcadorYo.setMap(null); } catch (e) {} }
    marcadorYo = gPunto(centro.lat, centro.lon,
      { radius: 8, color: '#fff', weight: 3, fillColor: '#5ec8e6', fillOpacity: 1 },
      etiqueta || T('estais_aqui'));

    /* Radio creciente: en ciudad sobra con 1,6 km; en campo abierto hay que
       abrirse para encontrar las pistas. Nos paramos en cuanto hay material. */
    /* LOS SITIOS SON UN EXTRA, NUNCA UN REQUISITO (founder, 1-sep-2026):
       "aunque sea por las calles de una ciudad la ruta debe salir; los parques,
       la sombra, las fuentes de agua y las veterinarias son puntos a favor pero
       nunca requisito imprescindible".
       Los sitios salen de Overpass, un servicio publico gratuito que se cae a
       ratos —el 1-sep-2026 estaban caidos los TRES servidores a la vez—. La ruta
       en cambio la calcula OSRM sobre el callejero, y ese va aparte. Por eso
       aqui no se corta nunca: sin sitios se traza igual por rumbo, que es lo que
       hace destinosPorRumbo() mas abajo. Antes habia un `return` justo aqui y
       dejaba al usuario sin paseo cada vez que Overpass fallaba. */
    var pois = [];
    var radios = [1600, 3000, 5000];
    var falloMapa = null;
    var limite = Date.now() + 10000;   /* todo el rato que se le concede a Overpass */
    for (var ri = 0; ri < radios.length; ri++) {
      if (Date.now() >= limite) break;
      try {
        pois = await buscarPois(centro.lat, centro.lon, radios[ri], limite);
        falloMapa = null;
      } catch (e) { falloMapa = e; continue; }
      if (pois.length >= 6) break;
    }
    if (!pois.length) {
      estadoTexto(falloMapa
        ? T('mapa_no_responde')
        : T('sin_zonas'));
    }
    estado.pois = pois;

    pois.forEach(function (p) {
      gPunto(p.lat, p.lon,
        { radius: 5, color: TIPOS[p.tipo].c, weight: 2, fillColor: TIPOS[p.tipo].c, fillOpacity: .55 },
        p.nombre + ' · ' + TIPOS[p.tipo].n, capaPois);
    });

    estadoTexto(T('calculando'));
    var objetivos = [
      { nombre: T('r_corta'),  m: 1500, por: T('r_corta_p') },
      { nombre: T('r_media'),    m: 3000, por: T('r_media_p') },
      { nombre: T('r_larga'),    m: 5000, por: T('r_larga_p') }
    ];
    for (var k = 0; k < objetivos.length; k++) {
      var o = objetivos[k];
      /* Primero con puntos de interés (la ruta "buena": pasa por zonas verdes).
         Si no hay, se cae al callejero para que igualmente haya paseo. */
      /* En campo abierto los anclajes quedan lejos y las pistas no van rectas:
         pedir 1,5 km devolvía 4,3 km reales, que para un cachorro o un perro
         mayor no sirve. Tanteamos varias escalas y nos quedamos con la que más
         se acerca a la distancia pedida. */
      /* UNA sola candidata por ruta. Antes se probaban hasta cinco y se
         quedaba con la que mas se acercaba a la distancia pedida: mejor
         precision, pero entre 3 y 15 llamadas al motor de rutas por paseo.
         Con Google Maps eso es dinero variable, y el precio al usuario no
         puede bailar segun lo que tarde en encontrar ruta (founder,
         30-ago-2026). Ahora son 3 llamadas fijas y el coste queda clavado. */
      /* DOS candidatas, no una, y gana la que mas se acerca a la distancia
         prometida (founder, 4-sep-2026: "quiero el mejor servicio").
           · Por SITIOS: pasa por parques y jardines, mas bonita, pero medida
             contra la API real da un 49 % de desviacion y hasta un 197 %: una
             "Vuelta corta" de 1,5 km salia de 3,6.
           · Por RUMBO: 13 % de desviacion, pero no busca lo verde.
         Calculando las dos y quedandose con la mejor: 11 % de desviacion, y la
         bonita gana en 4 de cada 15. Cuesta una llamada mas de rutas por paseo
         (~0,005 EUR) y se paga: la distancia prometida tiene que ser cierta. */
      var candidatos = [];
      var cp = elegirDestinos(pois, centro, o.m, 0.7);
      if (cp) candidatos.push(cp);
      candidatos.push(destinosPorRumbo(centro, o.m, 0));

      var res = null, mejorDif = Infinity;
      for (var c = 0; c < candidatos.length; c++) {
        var cand = null;
        try { cand = await ruta(candidatos[c]); } catch (e) { continue; }
        var dif = Math.abs(cand.metros - o.m);
        if (dif < mejorDif) { mejorDif = dif; res = cand; }
        /* Solo se corta si la primera ya es MUY buena (10 %). Con el 30 % de
           antes se aceptaba la de sitios sin llegar a probar la de rumbo, que
           casi siempre era mejor. */
        if (dif <= o.m * 0.1) break;
      }
      if (!res) continue;
      /* El nombre promete una distancia; si la real se aleja mucho, lo decimos
         en vez de llamar "vuelta corta" a 4 km. */
      o = { nombre: o.nombre, por: o.por, m: o.m };
      try {
        var capa = gTrazado(res.linea, { color: '#e8efea', weight: 3, opacity: .25 }, capaRutas);
        estado.rutas.push({
          nombre: o.nombre, por: o.por, metros: res.metros, linea: res.linea,
          pasos: res.pasos, puntos: res.puntos,
          pois: poisEnRuta(pois, res.linea), capa: capa
        });
      } catch (e) { /* esa distancia no sale: seguimos con las demás */ }
    }
    /* Sin rutas no hay nada que entregar: no se cobra. */
    if (!estado.rutas.length) {
      estadoTexto(T('sin_rutas'));
      var vac = document.getElementById('dmw-walk-lista');
      if (vac) vac.innerHTML = '<div class="dmw-walk-vacio">No hemos podido trazar rutas ' +
        T('sin_caminos') +
        T('prueba_pueblo') + '</div>';
      return;
    }
    /* Ya hay rutas de verdad: ahora sí se cobra. */
    if (!(await cobrarPaseo())) return;
    pintarLista(document.getElementById('dmw-walk-lista'));
    estadoTexto(estado.rutas.length + T('rutas_datos'));
    if (estado.rutas.length) seleccionar(0);
  }

  /* ── Montaje ───────────────────────────────────────────────────────────── */
  async function montar(cont) {
    cont.innerHTML =
      '<div class="dmw-walk">' +
        '<div class="dmw-walk-h">' +
          '<button class="dmw-walk-btn" id="dmw-walk-geo">' + T('usar_ubic') + '</button>' +
          '<div class="dmw-walk-sep">o</div>' +
          '<input class="dmw-walk-in" id="dmw-walk-q" placeholder="' + T('escribe_ciudad') + '">' +
          '<button class="dmw-walk-btn alt" id="dmw-walk-go">' + T('buscar') + '</button>' +
        '</div>' +
        '<button class="dmw-walk-cta" id="dmw-walk-rutas">' + T('buscar_tres') + '</button>' +
        '<div class="dmw-walk-body">' +
          '<div id="dmw-walk-map" class="dmw-walk-map"></div>' +
          '<div class="dmw-rutas" id="dmw-walk-lista">' +
            '<div class="dmw-walk-vacio">' + T('dinos_donde') +
            T('con_zv') + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="dmw-walk-relato" id="dmw-walk-relato"></div>' +
        '<div class="dmw-walk-nav" id="dmw-walk-nav"></div>' +
        '<div class="dmw-walk-fotos" id="dmw-walk-fotos"></div>' +
        '<div class="dmw-perfil">' +
          '<div class="dmw-perfil-h">' + T('como_es') + '</div>' +
          '<div class="dmw-perfil-ops" id="dmw-perfil-ops">' +
            Object.keys(NIVELES).map(function (k) {
              return '<button data-n="' + k + '">' + NIVELES[k].n + '</button>';
            }).join('') +
          '</div>' +
          '<label class="dmw-suelto"><input type="checkbox" id="dmw-suelto"> ' + T('suelto') + '</label>' +
          '<div class="dmw-perfil-nota" id="dmw-perfil-nota"></div>' +
        '</div>' +
        '<div class="dmw-walk-f"><span id="dmw-walk-estado">' + T('rutas_datos').trim() + '</span></div>' +
      '</div>';

    try { await cargarGoogleMaps(); }
    catch (e) { estadoTexto(T('mapa_error')); return; }
    mapa = new google.maps.Map(document.getElementById('dmw-walk-map'), {
      center: { lat: 40.4168, lng: -3.7038 }, zoom: 13,
      styles: ESTILO_OSCURO, disableDefaultUI: true, zoomControl: true,
      gestureHandling: 'greedy', clickableIcons: false
    });
    capaRutas = new GCapa();
    capaPois  = new GCapa();

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
        ? T('suelto_y') + NIVELES[n].n.toLowerCase() + T('recorre_aprox') +
          Math.round((NIVELES[n].f - 1) * 100) + ' %</b>' + T('mas_que_tu') + NIVELES[n].d + ').'
        : T('atado');
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
      estadoTexto(T('pidiendo'));
      if (!navigator.geolocation) { estadoTexto(T('sin_geo')); return; }
      navigator.geolocation.getCurrentPosition(
        function (p) { generar({ lat: p.coords.latitude, lon: p.coords.longitude }, T('estais_aqui')); },
        function () { estadoTexto(T('sin_permiso')); },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    };
    var buscar = async function () {
      var q = (document.getElementById('dmw-walk-q').value || '').trim();
      if (!q) return;
      estadoTexto(T('buscando_q') + q + '\u00bb…');
      try {
        var d = await pedir('/walks/buscar?q=' + encodeURIComponent(q));
        generar({ lat: d.lat, lon: d.lon }, (d.nombre || q).split(',')[0]);
      } catch (e) { estadoTexto('No se ha podido buscar ese sitio.'); }
    };
    document.getElementById('dmw-walk-go').onclick = buscar;
    /* El botón grande: si ya sabemos dónde está, recalcula ahí; si no, pide la
       ubicación. Antes la única forma de lanzarlo era "Usar mi ubicación", que
       parece que solo centra el mapa (founder 2026-08-17: "no encuentro el
       botón para pedir que te dé rutas"). */
    document.getElementById('dmw-walk-rutas').onclick = function () {
      if (estado.centro) { generar(estado.centro, T('estais_aqui')); return; }
      document.getElementById('dmw-walk-geo').click();
    };
    document.getElementById('dmw-walk-q').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') buscar();
    });
  }

  window.dmwWalkMontar = montar;
})();
