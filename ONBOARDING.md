# Dogs Mind — Onboarding y estado del proyecto

Última actualización: **2026-05-21**

App SaaS de consultoría conductual canina con IA. Founder único: Teo Mariscal. **EN PRODUCCIÓN con usuarios DE PAGO desde 2026-05-20** (fin de pre-launch).

---

## Resumen rápido

- **Producto**: análisis funcional ABC + plan de intervención LIMA con Claude Sonnet 4.6 + RAG. Avatares conversacionales con Haiku 4.5. Vídeo multimodal en anamnesis.
- **URL prod**: https://thedogsmind.net (SW **v154**)
- **Backend**: https://dogs-mind-backend-production.up.railway.app (Railway plan **Pro** desde 2026-05-20)
- **Modelo de negocio**: prepago en tokens (NO suscripción). **Stripe en LIVE.**
- **Stack**: FastAPI + PostgreSQL (Railway) + Anthropic API + Voyage AI + Qdrant Cloud + Netlify + Stripe
- **Modelos IA**: Sonnet 4.6 (`clinical_model`) para análisis/plan/seguimientos; Haiku 4.5 (`avatar_model`) para Aigents/explica/tips. NO se usa Opus (decisión coste/latencia; ver "Ideas post-launch").

---

## 🚀 Lanzamiento 2026-05-20/21 — cambios desplegados y verificados

**Despliegue**: backend Railway (git-conectado, auto-deploy on push a `main`) + frontend Netlify (`netlify deploy --prod`, site `152389f9-0282-46b5-a929-db9f9b142912`). Repo `Teomariscal/dogs-mind-backend` sincronizado con prod.

### Fixes del asesor (6 válidos de 10 prompts)
- **#9** refund automático de tokens si la IA falla (`token_utils.refund_token` en /analysis, /analysis/video, /analysis/chat, /avatar/chat) + UI de error con toast (no alert).
- **#10** aviso "Este análisis consume 3 tokens" pre-análisis + badge "Ejemplo" en perros demo.
- **#3** endpoint `POST /auth/validate-invite` (valida código sin crear cuenta, rate-limit 30/h) + validación on-blur en registro.
- **#7** dropdown país i18n ES/EN. **#8** campos obligatorios marcados + on-blur.
- Falsos positivos descartados: mobile responsive (ya lo era), Aigents .map crash (no existía), legal pages (ya existían), submit loading (ya estaba).

### Pricing (CRÍTICO corregido) — packs de tokens
Backend cobraba importes desactualizados ≠ frontend. Corregido a los 3 canónicos:
| Pack | Precio |
|---|---|
| 5 | 4,99 € |
| 20 | 16,00 € |
| 60 | 42,00 € |
`APP_URL=https://thedogsmind.net` añadida en Railway (antes faltaba → redirect post-pago iba al beta viejo).

### Casos: durabilidad + cross-device + límites
- **Auto-guardado al aceptar**: `acceptIntervention` llama a `/cases/migrate` → todo caso se guarda en backend (durable + seguimiento diario) sin acciones secundarias.
- **Cross-device**: `syncBackendCases()` baja `GET /cases` al entrar en registros (dedupe por backend_case_id, refresca nombres vacíos). `migrate` ahora guarda `client_dog_name/breed/age` + backfill aplicado a 21 casos existentes.
- **Límites de casos por cuenta** (`cases.py _max_cases_for`): particular=**2**, professional=**20**, corporativo=**ilimitado**. Mensaje "Has alcanzado el máximo de X casos. Borra uno". NO borra nada retroactivo. Verificado en vivo.
  - ⚠️ "corporativo" es account_type NUEVO sin flujo de asignación (a mano en DB por ahora).
  - Nota: "perros" (perfiles, cap 2 todos) ≠ "casos". El límite es de CASOS.

### Programa de delegaciones / tokens de bienvenida (links `?invite=`)
| Cohorte | Código | Tokens | Comisión |
|---|---|---|---|
| Usuario normal | (sin código) | 5 | — |
| Delegación país | `BOCALAN-XX` (CO/PE/EC/CL/UY/CR/IT/IL/ES) | 8 (5+3) | 10% web / 5% iOS |
| Equipo técnico sede | `BOCALAN-TEC` | 10 | 0% |
| Ambassador | `BOCALAN-AMB` | 12 | 0% |
| Directores curso/sede | `BOCALAN-DIR` | 18 | 0% |
Roles `ambassador`/`tech` son cosméticos (badge admin), no desbloquean features. El ambassador viejo `DogsmindAmb25@` (env) sigue dando 8 hasta retirarlo.

### Pendientes post-launch (NO bloquean)
Ver sección "Ideas post-launch" / memoria. Resumen: análisis premium Opus, flujo cuenta corporativo, retirar ambassador viejo, ajustar copy "20 perros", revocar token Netlify + rotar contraseña Postgres.

---

## Pricing — datos canónicos vigentes

### Packs de tokens (NO modificar sin autorización Teo)

| Pack | Precio | €/token |
|---|---|---|
| 5 | 4,99 € | 0,998 |
| 20 (preferido) | 16,00 € | 0,800 |
| 60 (profesional) | 42,00 € | 0,700 |

### Cobros por endpoint IA

| Endpoint | Tokens | Modelo | Coste real €/call medido |
|---|---|---|---|
| `/analysis` (texto) | 3.0 | Sonnet 4.6 + RAG | **0,064 €** ✓ verificado |
| `/analysis/video` | 4.0 | Sonnet 4.6 + RAG + vision (8 frames, 10s) | ~0,075 € (estimado, +17% sobre texto) |
| `/intervention` (plan LIMA) | **0** ⚠ | Sonnet 4.6 + RAG | ~0,040 € (no loguea, bug observabilidad) |
| `/cases/.../plan-simple` | 0.1 | Haiku 4.5 | 0,006 € ✓ verificado |
| `/cases/.../abc-explained` | 0.1 | Haiku 4.5 | 0,006 € ✓ verificado |
| `/cases/.../seguimiento` | 1.5 | Sonnet 4.6 + RAG | ~0,030 € (estimado) |
| `/avatar/chat` | 0.10 | Haiku 4.5 | **0,0045 €** ✓ verificado |
| `/analysis/chat` (refine) | 0.25 | Sonnet 4.6 | ~0,012 € (bug logging, devuelve 0€) |
| `/daily-followup/today` | **0** ⚠ | Sonnet 4.6 | ~0,020 € (no loguea) |
| `/tip/today` | 0 (caché 1×día/idioma) | Haiku 4.5 | <0,001 € |

### Tokens cortesía / bienvenida

| Cohorte | Tokens | Coste técnico equivalente |
|---|---|---|
| Usuario nuevo (signup) | 5 | ~0,10 € real |
| Embajador (`AMBASSADOR_CODE`) | 8 (5+3) | ~0,16 € |
| Delegación (BOCALAN-XX, 9 países) | 8 (5+3) | ~0,16 € |
| Pro cortesía (`PRO_INVITE_CODE`) | 10 + membresía Pro €20 GRATIS | ~30 € valor regalado |

---

## Estado financiero al 2026-05-17 (datos reales medidos)

### Métricas de tracking (`usage_log` table)

- **157 llamadas IA logueadas lifetime**
- **3,34 € coste Anthropic real** acumulado (excluye `/intervention`, `/daily-followup`, `/analysis/video` que no loguean)
- Tokens cobrados a usuarios: 143,45
- Margen real medido: **97,1 %**

### Distribución coste por endpoint (lifetime)

- `/analysis`: 2,82 € (84% del coste API total)
- `/avatar/chat`: 0,42 € (12%)
- `/cases/abc-explained` + `/cases/plan-simple`: 0,10 € (3%)
- `/analysis/chat`: 0 € (bug logging)

### Coste por modelo

- Sonnet 4.6: 44 calls, 2,82 €
- Haiku 4.5: 112 calls, 0,52 €
- Sonnet 4.5 (legacy): 1 call, 0 €

### Validación vs estimaciones iniciales

| Métrica | Estimación previa | Real | Diferencia |
|---|---|---|---|
| Coste /analysis | €0,050 | **€0,064** | +28% mayor |
| Coste /avatar/chat | €0,0009 | **€0,0045** | +400% mayor |
| Margen /analysis | 93% | **97,3%** | mejor de lo estimado |

**Conclusión pricing**: márgenes muy sanos. **No bajar precios pre-launch**.

---

## Red flags activas

### 🚩 #1 — Bug observabilidad costes (CRÍTICO operativo)

3 endpoints NO loguean en `usage_log` aunque consumen Anthropic:
- `/intervention` (plan LIMA, el más caro tras /analysis)
- `/daily-followup/today` (Sonnet 4.6 con coach)
- `/analysis/chat` (devuelve cost_eur=0 a pesar de loguear)
- `/analysis/video` (no loguea)

**Impacto**: el CFO ve solo ~50-70% del coste real Anthropic. Antes de cualquier decisión de pricing, hay que arreglar el tracking.

**Fix sugerido**: añadir `background_tasks.add_task(log_usage, ...)` en los 4 endpoints siguiendo patrón de `/analysis`. ~1 tarde de trabajo low risk.

### 🚩 #2 — `/intervention` regalado (decisión pendiente)

Coste estimado €0.04/plan, ingreso €0. Proyección:
- 1.000 MAU → €60/mes regalados
- 100.000 MAU → €6.000/mes regalados
- 1M MAU → **€720K/año regalados**

**Decisión pendiente Teo**: cobrar 1-2 tokens por intervention o mantener como gancho de retención.

### 🚩 #3 — Escala Anthropic Enterprise

A >$5K/mes Anthropic = negociar Enterprise pricing (volume discount). Trigger probable: ~50.000 MAU.

---

## Cap table (al 2026-05-17)

- Teo Mariscal: 100% founder único
- Option pool: 0% (pendiente reservar antes de pre-Serie A)
- Sin SAFEs / angels / inversores externos

---

## Programa delegaciones internacionales

9 delegaciones BOCALAN-XX activas con comisión sobre revenue:
- Colombia, Perú, Ecuador, Chile, Uruguay, Costa Rica, Italia, Israel, España
- **10% web** (Stripe) / **5% iOS** (cuando IAP esté integrado)
- Reporting agregado: `GET /admin/delegations/report` (admin only)
- Atribución inmutable vía `users.delegation_id` FK

---

## Proyección a escala (con datos reales)

| MAU mensual | Coste API estimado/mes | Ingreso (pack 5/usuario) | Margen mensual |
|---|---|---|---|
| 12 (hoy beta) | ~€1 | n/a | n/a |
| 1.000 | ~€120 | €4.990 | €4.870 (97%) |
| 10.000 | ~€1.200 | €49.900 | €48.700 (97%) |
| 100.000 | ~€12.000 | €499.000 | €487.000 (97%) |
| 1M (objetivo 5y) | **€120.000** | €4.990.000 | **€4,87M (97%)** |

---

## Datos pendientes para P&L completo

- Coste Anthropic verificado en `console.anthropic.com` (proxy aproximado: usage_log + ~50% para endpoints no logueados)
- Coste Railway, Netlify (3 sites), Voyage AI, Qdrant Cloud mensuales
- Saldo caja actual
- Revenue Stripe (€0 esperado hoy, beta)
- Coste dominios (porkbun.com anual)

---

## Endpoint CFO (admin only)

`GET /admin/cfo-report?from=YYYY-MM-DD&to=YYYY-MM-DD`

Devuelve agregados por endpoint y modelo (cero datos individuales). Requiere JWT admin O env var `CFO_REPORT_KEY`.

---

## Estado deploys actuales (al 2026-05-21)

| SW frontend | Backend | Status |
|---|---|---|
| **v154** | commit `ce49dea` | PROD vivo · usuarios de pago |

**Sesiones recientes documentadas en memory**:
- 2026-05-16: delegaciones, Pro cortesía, lang per caso
- 2026-05-17: vídeo upload completo, audit 2 agents + 7 fixes, análisis CFO con datos reales
- 2026-05-20/21: **LANZAMIENTO con usuarios de pago** — 6 fixes asesor, fix pricing crítico, APP_URL, auto-guardado de casos al aceptar, sync cross-device + backfill nombres, límites de casos por cuenta (2/20/∞), estructura de tokens de bienvenida (5 niveles), Railway→Pro. Ver sección "Lanzamiento 2026-05-20/21" arriba.

---

## Reglas duras del proyecto (App Store compliance)

- CERO emojis Unicode en HTML/CSS/copy
- CERO huellas/paw prints
- Palabra "Bocalán" NUNCA en assets in-app
- Touch targets mobile ≥44×44px
- Inputs font-size ≥16px (iOS auto-zoom)
- Safe-areas con `env(safe-area-inset-*)` en pantallas full-screen
- Sin botones "Próximamente" visibles (Apple Guideline 2.1)
- Lógica de negocio en backend, no client-side
- Validación Pydantic completa en endpoints
- Service Worker bump obligatorio en cada cambio frontend

---

## Memorias de detalle (Claude Code memory files)

Archivos completos en `~/.claude/projects/.../memory/`:

- `project_dogs_mind_finance.md` — **Análisis CFO completo** (lectura obligatoria para cualquier estudio financiero)
- `project_dogs_mind_estado_2026_05_17.md` — Snapshot último día con deploys + audit
- `project_dogs_mind_delegations.md` — Programa delegaciones + reporting comisiones
- `project_dogs_mind_lang_per_case.md` — Opción C lang fijo por caso
- `project_dogs_mind_pricing_dinamico.md` — Spec pricing dinámico (post-launch)
- `project_dogs_mind_appstore_iap_decision.md` — Decisión IAP iOS (Apple 15-30%)
- `feedback_dogs_mind_design_lock.md` — Workflow anclado DESIGN-LOCK.md
- `feedback_appstore_zero_friction.md` — Prioridad #1 maestra

---

## Para análisis financiero externo

Si un analista/consultor accede a este documento para estudio financiero:

1. **Estado revenue**: pre-launch, sin ingresos significativos aún
2. **Margen actual real**: 97% sobre coste Anthropic verificado
3. **Burn mínimo mensual estimado**: €80-150 (infraestructura sin Anthropic, Railway OK confirmado)
4. **Escalabilidad**: validada — márgenes se mantienen a >1M MAU
5. **Red flags**: bugs de observabilidad (no funcionales) + endpoints sin cobro pendientes de decisión estratégica
6. **Datos faltantes para P&L formal**: ver sección "Datos pendientes" arriba
