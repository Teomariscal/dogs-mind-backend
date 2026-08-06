# Dogs Mind — GATE anti-rechazo pre-launch

**Regla del founder (2026-06-09):** máximos recursos anti-rechazo, el coste NUNCA por encima
de la efectividad. Este gate se ejecuta **antes de CADA intento de submit a App Store**. Solo
se pulsa "Enviar" si el gate sale **VERDE (cero blockers)**.

## Cuándo se corre
- **NO ahora** (el build aún tiene blockers conocidos: IAP sin cablear, pantallas Pro con
  precios Stripe, 4.2 sin features nativas). Correrlo hoy solo re-encontraría lo ya sabido.
- **SÍ justo antes de submitir**, una vez cerrados los blockers (IAP integrado, etc.).
- Se re-corre tras cada fix hasta que quede verde.

## Composición del gate (máximos recursos)
1. **Barrido multi-agente por guideline** (como el audit del 2026-06-08): un agente "revisor
   de Apple" por cada guideline (3.1.1, 3.1.2, 4.2, 4.7, 5.1.1, 5.1.2, 2.1, 2.3.x, 4.1,
   metadata, Info.plist/perm, 2.5.2…), sobre el código + binario + docs REALES. Agentes en
   **modo solo-lectura** (Explore) para que no editen nada durante la auditoría.
2. **Verificación adversarial con el modelo más potente (advisor strategy):** cada hallazgo lo
   confirma/refuta un verificador fuerte (Fable 5 cuando esté disponible; mientras, Opus),
   ≥2 verificadores por hallazgo crítico, perspectivas distintas. Descartar falsos positivos.
3. **"Revisor de Apple simulado" end-to-end:** un pase final que recorre la app como App Review
   (flujo de compra IAP, login con cuenta demo, cámara/permisos, cuenta/borrado) buscando
   cualquier motivo de rechazo.
4. **Code-review por agentes** de las piezas de riesgo (IAP/RevenueCat, webhooks, signing).
5. **Smoke tests funcionales** en TestFlight/simulador (device-side) — complementa lo estático;
   el gate de agentes NO sustituye correr la app de verdad.

## Salida
- Lista priorizada: blockers / high / medium / low + evidencia + fix, con falsos positivos
  descartados y razonamiento del verificador.
- **Criterio de submit:** 0 blockers y 0 high sin mitigar. Cada hallazgo confirmado se arregla
  y se vuelve a pasar el gate.

## Límite honesto
Cubre compliance + código + lógica (estático + razonamiento). NO sustituye la revisión real de
Apple ni el QA funcional en dispositivo — por eso incluye el punto 5. Reduce el riesgo de
rechazo al mínimo, no lo elimina al 0%.

## Historial
- 2026-06-08: primera corrida (51 agentes) → 7 blockers, 2 high, 18 falsos positivos. Resultado
  en el transcript del workflow. Caza un agujero real de D-002 (pantallas Pro con Stripe).

Related: `APPSTORE_COMPLIANCE.md`, `APPSTORE_DECISIONS.md`, `APPSTORE_IAP_PLAN.md`, `APPSTORE_TESTFLIGHT_ISSUES.md`.
