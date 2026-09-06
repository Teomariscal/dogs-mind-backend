/* ─────────────────────────────────────────────────────────────────────────
   DETECTOR DE FUGAS — EN VIVO

   Recorre la app de verdad en las seis combinaciones (es · en · it) x
   (conductual · cognitivista) y lee el texto REALMENTE VISIBLE de cada
   pantalla. Lo estatico no basta: un nodo puede existir en el HTML y no
   verse, o verse solo en un idioma. Aqui se mira offsetParent y display,
   no textContent a secas — ese fue el falso positivo del 6-sep-2026.

   Se pega en la consola del navegador con la app cargada. Deja el resultado
   en window._fugas.

   Regla: fuera de (it + cognitive) no puede verse NI UNA palabra CZ.
   Y dentro de (it + cognitive) no puede verse NI UNA palabra ABA.
   ───────────────────────────────────────────────────────────────────────── */
(function () {
  var CZ = ['zooantropolog','marchesini','tassonomia','appraisal','arousal','coping',
            'evocator','emendativ','emendazione','surrogata','rappresentazional',
            'umwelt','serendipity','referenzialit','detour','cooling-down','prossemica',
            'iper-polarizzazione','neglette','epimeletic','sillectic','perlustrativ',
            'somestesic','cinestesic'];
  var ABA = ['rinforzo','rinforzare','estinzione','condizionamento operante','operante',
             'stimolo discriminante','stimolo discriminativo','analisi funzionale',
             'comportamentismo','token economy','shaping','chaining','abc',
             'refuerzo','extinción','estímulo discriminativo'];

  function visible(el) {
    if (!el) return false;
    if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') return false;
    var s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
  }

  /* Solo hojas: si se cogiera el textContent del padre se contaria lo oculto. */
  function textoVisible(raiz) {
    if (!raiz) return '';
    var out = [];
    raiz.querySelectorAll('*').forEach(function (e) {
      if (e.children.length === 0 && visible(e)) {
        var t = (e.textContent || '').trim();
        if (t) out.push(t);
      }
      /* los placeholders y los value tambien se leen */
      if (visible(e)) {
        if (e.placeholder) out.push(e.placeholder);
        if (e.tagName === 'OPTION' && e.textContent) out.push(e.textContent);
      }
    });
    return out.join(' · ').toLowerCase();
  }

  function buscar(txt, lista) {
    return lista.filter(function (p) { return txt.indexOf(p) !== -1; });
  }

  var esperar = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  window._fugas = { casos: [], fugasCZ: [], fugasABA: [] };

  window.dmComprobarFugas = async function (pantallas) {
    pantallas = pantallas || ['s-home','s-anamnesis','s-records','s-planes','s-avatars'];
    var langs = ['es','en','it'];
    var vias  = ['behavioral','cognitive'];

    for (var li = 0; li < langs.length; li++) {
      for (var vi = 0; vi < vias.length; vi++) {
        var L = langs[li], V = vias[vi];
        try { setLang(L); } catch (e) {}
        window._tdmStance = V;
        try { if (typeof refreshStanceSelector === 'function') refreshStanceSelector(); } catch (e) {}
        await esperar(250);

        for (var pi = 0; pi < pantallas.length; pi++) {
          var p = pantallas[pi];
          if (!document.getElementById(p)) continue;
          try { goTo(p); } catch (e) { continue; }
          await esperar(350);
          var txt = textoVisible(document.getElementById(p));
          var cz  = buscar(txt, CZ);
          var aba = buscar(txt, ABA);
          var esCognitivo = (L === 'it' && V === 'cognitive');

          window._fugas.casos.push({ lang: L, via: V, pantalla: p, cz: cz, aba: aba });

          /* CZ fuera de it+cognitive = EBOLA */
          if (cz.length && !esCognitivo) {
            window._fugas.fugasCZ.push({ lang: L, via: V, pantalla: p, palabras: cz });
          }
          /* ABA dentro de it+cognitive = resfriado, pero se anota */
          if (aba.length && esCognitivo) {
            window._fugas.fugasABA.push({ lang: L, via: V, pantalla: p, palabras: aba });
          }
        }
      }
    }
    try { setLang('es'); } catch (e) {}
    window._tdmStance = 'behavioral';
    window._fugas.fin = true;
    window._fugas.resumen = {
      casos: window._fugas.casos.length,
      EBOLA_cz_fuera_de_it_cognitive: window._fugas.fugasCZ.length,
      resfriado_aba_dentro_de_cognitive: window._fugas.fugasABA.length
    };
    return window._fugas.resumen;
  };
})();
