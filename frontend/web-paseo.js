/* ═══════════════════════════════════════════════════════════════════════════
   EL PASEO DE HOY — tarjeta en el inicio + planificador a pantalla completa
   ---------------------------------------------------------------------------
   SOLO WEB. Lo carga dmInitWebLayer(), que no se ejecuta dentro de las apps
   nativas; además vuelve a comprobarlo aquí. En el móvil web se ve igual que
   se vería en la app, que es justo lo que queremos validar antes de tocarla.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  try {
    if (typeof window.dmIsNativeApp === 'function' && window.dmIsNativeApp()) return;
    if (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()) return;
    if (!document.body || !document.body.classList.contains('dm-web')) return;
  } catch (e) { return; }

  var CSS = ''
  + '#paseo-card{display:block;width:100%;text-align:left;font-family:inherit;cursor:pointer;'
  +   'color:#e8efea;margin:14px 0 2px;padding:15px;border-radius:20px;'
  +   'background:linear-gradient(135deg,rgba(126,184,106,.18),rgba(94,200,230,.13));'
  +   'border:1.5px solid rgba(126,184,106,.45);box-shadow:0 8px 24px rgba(0,0,0,.30);'
  +   'transition:transform .12s ease;}'
  + '#paseo-card:active{transform:scale(.99);}'
  + '.pc-top{display:flex;align-items:center;gap:12px;}'
  /* Ale, la Aigent que acompaña el paseo (founder 2026-07-29) */
  + '.pc-ic{width:52px;height:52px;flex:none;border-radius:50%;overflow:hidden;'
  +   'border:2px solid #7eb86a;box-shadow:0 0 0 3px rgba(94,200,230,.18);background:rgba(126,184,106,.15);}'
  + '.pc-ic img{width:100%;height:100%;object-fit:cover;display:block;}'
  + '.pc-t{display:block;font-family:var(--ff-serif,serif);font-size:20px;font-weight:600;line-height:1.1;color:#fff;}'
  + '.pc-s{display:block;font-size:12px;color:rgba(232,239,234,.62);margin-top:3px;}'
  + '.pc-km{display:flex;gap:8px;margin-top:13px;}'
  + '.pc-km span{flex:1;text-align:center;font-size:12.5px;font-weight:600;color:#80d6ee;'
  +   'background:rgba(94,200,230,.10);border:1px solid rgba(94,200,230,.30);border-radius:100px;padding:7px 0;}'
  /* Pantalla completa del planificador */
  + '#paseo-full{position:fixed;inset:0;z-index:9000;display:none;flex-direction:column;'
  +   'background:linear-gradient(180deg,#0a1a14 0%,#14302a 60%,#1a3b2e 100%);}'
  + '#paseo-full.on{display:flex;}'
  + '.pf-bar{display:flex;align-items:center;gap:12px;padding:calc(env(safe-area-inset-top,0px) + 14px) 16px 12px;'
  +   'border-bottom:1px solid rgba(232,239,234,.10);}'
  + '.pf-x{width:38px;height:38px;flex:none;border-radius:50%;background:rgba(255,255,255,.08);'
  +   'border:1px solid rgba(255,255,255,.20);color:#e8efea;font-size:16px;cursor:pointer;}'
  + '.pf-ale{width:40px;height:40px;flex:none;border-radius:50%;overflow:hidden;'
  +   'border:2px solid #7eb86a;box-shadow:0 0 0 2px rgba(94,200,230,.18);}'
  + '.pf-ale img{width:100%;height:100%;object-fit:cover;display:block;}'
  + '.pf-tt{font-family:var(--ff-serif,serif);font-size:20px;font-weight:600;color:#fff;line-height:1.1;}'
  + '.pf-ts{display:block;font-family:var(--ff-sans,sans-serif);font-size:11.5px;color:#5ec8e6;letter-spacing:.4px;}'
  + '.pf-body{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:0 14px 14px;}'
  /* Hero + presentación de Ale (copy del founder 2026-07-29) */
  + '.pf-hero{position:relative;margin:0 -14px 0;height:210px;overflow:hidden;}'
  + '.pf-hero img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block;}'
  + '.pf-hero::after{content:"";position:absolute;inset:0;'
  +   'background:linear-gradient(0deg,rgba(10,26,20,1) 2%,rgba(10,26,20,.55) 45%,rgba(10,26,20,.10) 100%);}'
  + '.pf-hero-cap{position:absolute;left:16px;bottom:12px;z-index:2;font-size:10.5px;'
  +   'letter-spacing:1.8px;text-transform:uppercase;color:rgba(232,239,234,.62);font-weight:600;}'
  /* La presentación empieza DEBAJO de la foto: Ale no la pisa */
  + '.pf-intro{position:relative;margin:16px 0 18px;padding:0 2px;z-index:1;}'
  /* Ale agachada con su perra (ilustración original, fondo transparente):
     pequeña y debajo de la foto, sin pisarla. La versión recortada del grupo
     cortaba la cara de la perra → descartada (founder 2026-07-30). */
  + '.pf-intro-top{display:flex;align-items:flex-end;gap:12px;margin-bottom:14px;}'
  + '.pf-intro-ale{flex:none;width:132px;margin-bottom:-2px;'
  +   'filter:drop-shadow(0 8px 18px rgba(0,0,0,.55));}'
  + '.pf-intro-ale img{width:100%;height:auto;display:block;}'
  + '.pf-intro-n{font-family:var(--ff-serif,serif);font-size:22px;font-weight:600;color:#fff;'
  +   'line-height:1.1;padding-bottom:10px;}'
  + '.pf-intro-n small{display:block;font-family:var(--ff-sans,sans-serif);font-size:11px;'
  +   'letter-spacing:1.4px;text-transform:uppercase;color:#7eb86a;font-weight:600;margin-top:3px;}'
  + '.pf-claim{font-size:14.5px;line-height:1.65;color:rgba(232,239,234,.88);margin-bottom:12px;}'
  + '.pf-challenge{border-left:2px solid #5ec8e6;padding-left:13px;font-size:13.5px;'
  +   'line-height:1.6;color:rgba(232,239,234,.72);}'
  + '.pf-challenge b{color:#80d6ee;font-weight:600;}'
  /* El planificador en móvil: mapa arriba, rutas debajo */
  + '@media (max-width:1023px){'
  +   '#paseo-full .dmw-walk{border:1px solid rgba(94,200,230,.35);border-radius:18px;overflow:hidden;'
  +     'background:linear-gradient(180deg,rgba(20,48,42,.96),rgba(10,26,20,.96));}'
  +   '#paseo-full .dmw-walk-h{display:flex;flex-wrap:wrap;gap:8px;padding:12px;'
  +     'border-bottom:1px solid rgba(232,239,234,.10);}'
  +   '#paseo-full .dmw-walk-btn{font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;'
  +     'padding:10px 14px;border-radius:100px;border:none;color:#fff;'
  +     'background:linear-gradient(135deg,#7eb86a,#4a6741);}'
  +   '#paseo-full .dmw-walk-btn.alt{background:rgba(94,200,230,.12);border:1.5px solid rgba(94,200,230,.45);}'
  +   '#paseo-full .dmw-walk-sep{font-size:12px;color:rgba(232,239,234,.38);align-self:center;}'
  +   '#paseo-full .dmw-walk-in{flex:1;min-width:150px;font-family:inherit;font-size:16px;padding:10px 14px;'
  +     'border-radius:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.18);color:#fff;outline:none;}'
  +   '#paseo-full .dmw-walk-body{display:block;}'
  +   '#paseo-full .dmw-walk-map{height:260px;background:#0a1a14;}'
  +   '#paseo-full .dmw-rutas{display:flex;flex-direction:column;gap:10px;padding:12px;'
  +     'border-top:1px solid rgba(232,239,234,.10);}'
  +   '#paseo-full .dmw-ruta-c{text-align:left;font-family:inherit;cursor:pointer;color:#e8efea;'
  +     'background:rgba(255,255,255,.05);border:1px solid rgba(232,239,234,.10);border-radius:14px;padding:13px;}'
  +   '#paseo-full .dmw-ruta-c.on{border-color:#5ec8e6;background:rgba(94,200,230,.10);}'
  +   '#paseo-full .dmw-ruta-top{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:5px;}'
  +   '#paseo-full .dmw-ruta-top b{font-size:15px;color:#fff;}'
  +   '#paseo-full .dmw-ruta-top span{font-size:12.5px;color:#80d6ee;font-weight:600;white-space:nowrap;}'
  +   '#paseo-full .dmw-ruta-c p{margin:0 0 10px;font-size:13px;line-height:1.5;color:rgba(232,239,234,.62);}'
  +   '#paseo-full .dmw-ruta-tags{display:flex;flex-wrap:wrap;gap:6px;}'
  +   '#paseo-full .dmw-ruta-tags span{font-size:11.5px;padding:4px 10px;border-radius:100px;'
  +     'background:rgba(126,184,106,.14);border:1px solid rgba(126,184,106,.35);color:#a9d69a;}'
  +   '#paseo-full .dmw-walk-fotos{padding:12px;border-top:1px solid rgba(232,239,234,.10);}'
  +   '#paseo-full .dmw-fotos-h{font-size:10.5px;letter-spacing:1.8px;text-transform:uppercase;'
  +     'font-weight:700;color:#5ec8e6;margin-bottom:10px;}'
  +   '#paseo-full .dmw-fotos-row{display:grid;grid-auto-flow:column;grid-auto-columns:140px;gap:10px;overflow-x:auto;}'
  +   '#paseo-full .dmw-foto{display:block;text-decoration:none;border-radius:12px;overflow:hidden;'
  +     'border:1px solid rgba(232,239,234,.10);background:rgba(255,255,255,.05);}'
  +   '#paseo-full .dmw-foto img{width:100%;height:88px;object-fit:cover;display:block;}'
  +   '#paseo-full .dmw-foto span{display:block;padding:7px 9px;font-size:11px;color:rgba(232,239,234,.62);'
  +     'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}'
  +   '#paseo-full .dmw-fotos-cred,#paseo-full .dmw-walk-f{font-size:11px;color:rgba(232,239,234,.38);padding:8px 12px;}'
  +   '#paseo-full .dmw-walk-relato{padding:12px;border-top:1px solid rgba(232,239,234,.10);}'
  +   '#paseo-full .dmw-relato-h{font-size:10.5px;letter-spacing:1.8px;text-transform:uppercase;'
  +     'font-weight:700;color:#7eb86a;margin-bottom:10px;}'
  +   '#paseo-full .dmw-relato p{margin:0 0 10px;font-size:14px;line-height:1.7;color:#e8efea;}'
  +   '#paseo-full .dmw-relato-f,#paseo-full .dmw-relato-cargando{font-size:11.5px;line-height:1.5;'
  +     'color:rgba(232,239,234,.38);}'
  +   '#paseo-full .dmw-walk-nav{padding:12px;border-top:1px solid rgba(232,239,234,.10);}'
  +   '#paseo-full .dmw-nav-h{font-size:10.5px;letter-spacing:1.8px;text-transform:uppercase;'
  +     'font-weight:700;color:#5ec8e6;margin-bottom:10px;}'
  +   '#paseo-full .dmw-nav-pasos{margin:0 0 14px;padding-left:20px;}'
  +   '#paseo-full .dmw-nav-pasos li{font-size:13.5px;line-height:1.55;color:#e8efea;margin-bottom:6px;}'
  +   '#paseo-full .dmw-nav-pasos li.mas{list-style:none;margin-left:-20px;'
  +     'color:rgba(232,239,234,.38);font-size:12.5px;}'
  +   '#paseo-full .dmw-nav-btns{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;}'
  +   '#paseo-full .dmw-nav-btn{text-decoration:none;font-size:13.5px;font-weight:700;'
  +     'padding:12px 22px;border-radius:100px;color:#fff;'
  +     'background:linear-gradient(135deg,#7eb86a,#4a6741);box-shadow:0 4px 14px rgba(74,103,65,.35);}'
  +   '#paseo-full .dmw-nav-btn.alt{background:rgba(94,200,230,.12);color:#e8efea;'
  +     'border:1.5px solid rgba(94,200,230,.45);box-shadow:none;}'
  +   '#paseo-full .dmw-nav-nota,#paseo-full .dmw-nav-vacio{font-size:12px;line-height:1.5;'
  +     'color:rgba(232,239,234,.38);}'
  +   '#paseo-full .dmw-perfil{padding:12px;border-top:1px solid rgba(232,239,234,.10);}'
  +   '#paseo-full .dmw-perfil-h{font-size:10.5px;letter-spacing:1.8px;text-transform:uppercase;'
  +     'font-weight:700;color:#5ec8e6;margin-bottom:10px;}'
  +   '#paseo-full .dmw-perfil-ops{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;}'
  +   '#paseo-full .dmw-perfil-ops button{font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;'
  +     'padding:8px 14px;border-radius:100px;color:#e8efea;background:rgba(255,255,255,.05);'
  +     'border:1px solid rgba(232,239,234,.10);}'
  +   '#paseo-full .dmw-perfil-ops button.on{background:rgba(94,200,230,.12);border-color:#5ec8e6;color:#fff;}'
  +   '#paseo-full .dmw-suelto{display:flex;align-items:center;gap:8px;font-size:13px;'
  +     'color:rgba(232,239,234,.62);margin-bottom:10px;}'
  +   '#paseo-full .dmw-perfil-nota{font-size:12.5px;line-height:1.55;color:rgba(232,239,234,.62);}'
  +   '#paseo-full .dmw-perfil-nota b{color:#7eb86a;}'
  +   '#paseo-full .dmw-perro-km{margin:0 0 10px;font-size:12.5px;color:rgba(232,239,234,.62);}'
  +   '#paseo-full .dmw-perro-km b{color:#7eb86a;font-size:13.5px;}'
  +   '#paseo-full .dmw-perro-km span{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
  +     'color:rgba(232,239,234,.38);border-bottom:1px dotted rgba(232,239,234,.38);}'
  +   '#paseo-full .dmw-walk-vacio,#paseo-full .dmw-fotos-cargando,#paseo-full .dmw-fotos-vacio{'
  +     'font-size:13px;color:rgba(232,239,234,.62);padding:12px;}'
  + '}';

  var st = document.createElement('style');
  st.textContent = CSS;
  document.head.appendChild(st);

  function abrir() {
    var f = document.getElementById('paseo-full');
    if (!f) return;
    f.classList.add('on');
    var host = f.querySelector('.pf-body');
    if (host.getAttribute('data-listo')) return;
    host.setAttribute('data-listo', '1');

    /* Cabecera: hero + Ale presentando la sección (copy del founder) */
    var cab = document.createElement('div');
    cab.innerHTML =
      '<div class="pf-hero"><img src="assets/images/soho-paseo.webp?v=2" alt="Escaparate en Soho, Nueva York">' +
        '<span class="pf-hero-cap">Soho · Nueva York</span></div>' +
      '<div class="pf-intro">' +
        '<div class="pf-intro-top">' +
          '<span class="pf-intro-ale"><img src="aig-ale.webp" alt="Ale con su perra"></span>' +
          '<span class="pf-intro-n">Ale<small>Tu Aigent de paseos</small></span>' +
        '</div>' +
        '<p class="pf-claim">Estés en el lugar del mundo que estés, te ayudamos a elegir ' +
        'las mejores y más seguras rutas para pasear con tu perro.</p>' +
        '<p class="pf-challenge">Antes, encontrar dónde pasear en una ciudad desconocida era ' +
        'el <b>reto</b>. Ahora el único <b>reto</b> es que tu perro disfrute como nunca, y seguro.</p>' +
      '</div>';
    host.appendChild(cab);

    var caja = document.createElement('div');
    host.appendChild(caja);
    if (window.dmwWalkMontar) { window.dmwWalkMontar(caja); return; }
    var s = document.createElement('script');
    s.src = 'web-walk.js?v=9';
    s.onload = function () { if (window.dmwWalkMontar) window.dmwWalkMontar(caja); };
    document.head.appendChild(s);
  }
  function cerrar() {
    var f = document.getElementById('paseo-full');
    if (f) f.classList.remove('on');
  }

  function montarFull() {
    if (document.getElementById('paseo-full')) return;
    var f = document.createElement('div');
    f.id = 'paseo-full';
    f.innerHTML =
      '<div class="pf-bar">' +
        '<button class="pf-x" aria-label="Cerrar">&#10005;</button>' +
        '<span class="pf-ale"><img src="aig-ale-pixar.webp" alt="Ale"></span>' +
        '<div><span class="pf-tt">El paseo de hoy</span>' +
        '<span class="pf-ts">con Ale · World Wide Dog Walking</span></div>' +
      '</div>' +
      '<div class="pf-body"></div>';
    f.querySelector('.pf-x').onclick = cerrar;
    document.body.appendChild(f);
  }

  function montarTarjeta() {
    var hero = document.querySelector('#s-home .hero-banner');
    if (!hero || document.getElementById('paseo-card')) return;
    var c = document.createElement('button');
    c.id = 'paseo-card';
    c.innerHTML =
      '<span class="pc-top">' +
        '<span class="pc-ic"><img src="aig-ale-pixar.webp" alt="Ale"></span>' +
        '<span><span class="pc-t">El paseo de hoy</span>' +
        '<span class="pc-s">Tres rutas cerca de ti</span></span>' +
      '</span>' +
      '<span class="pc-km"><span>corta</span><span>media</span><span>larga</span></span>';
    c.onclick = abrir;
    hero.parentNode.insertBefore(c, hero.nextSibling);
  }

  function init() { montarFull(); montarTarjeta(); }
  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
  /* La home se repinta al iniciar sesión: reintentamos un rato. */
  var t = setInterval(function () {
    if (document.getElementById('paseo-card')) { clearInterval(t); return; }
    montarTarjeta();
  }, 1500);
  setTimeout(function () { clearInterval(t); }, 60000);
})();
