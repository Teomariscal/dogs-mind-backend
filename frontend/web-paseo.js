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
  + '.pc-ic{width:44px;height:44px;flex:none;border-radius:14px;display:flex;align-items:center;'
  +   'justify-content:center;background:rgba(126,184,106,.20);border:1px solid rgba(126,184,106,.45);color:#7eb86a;}'
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
  + '.pf-tt{font-family:var(--ff-serif,serif);font-size:20px;font-weight:600;color:#fff;line-height:1.1;}'
  + '.pf-ts{display:block;font-family:var(--ff-sans,sans-serif);font-size:11.5px;color:#5ec8e6;letter-spacing:.4px;}'
  + '.pf-body{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:14px;}'
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
    if (window.dmwWalkMontar) { window.dmwWalkMontar(host); return; }
    var s = document.createElement('script');
    s.src = 'web-walk.js?v=4';
    s.onload = function () { if (window.dmwWalkMontar) window.dmwWalkMontar(host); };
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
        '<div><span class="pf-tt">El paseo de hoy</span>' +
        '<span class="pf-ts">World Wide Dog Walking</span></div>' +
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
        '<span class="pc-ic">' +
          '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" ' +
          'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">' +
          '<path d="M12 21s7-6.1 7-11a7 7 0 1 0-14 0c0 4.9 7 11 7 11Z"/>' +
          '<circle cx="9.6" cy="8.2" r="1"/><circle cx="14.4" cy="8.2" r="1"/>' +
          '<circle cx="12" cy="11.6" r="1.7"/></svg>' +
        '</span>' +
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
