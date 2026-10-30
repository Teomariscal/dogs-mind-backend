# Ficha italiana de la App Store — preparada, sin enviar

Founder, 30-oct-2026: *"prepararlo y envialo a appstore"* → se eligió la
**opción A**: no se retira la 1.0.38 que ya está en cola (añadir un idioma
después de enviar lo prohíbe Apple, y retirar el envío cuesta el sitio en la
cola). Esto entra en la **1.0.39**.

    HTTP 409 — "Cannot create localization after the app version
                has been submitted for review."

---

## LO QUE APPLE EXIGE PARA AÑADIR UN IDIOMA

No es traducir una descripción. Por idioma hacen falta:

| nivel | campo | estado |
|---|---|---|
| ficha (`appInfoLocalizations`) | nombre | listo abajo |
| ficha | subtítulo | listo abajo |
| ficha | URL de privacidad | la misma |
| versión (`appStoreVersionLocalizations`) | descripción | **traducción abajo, pendiente de que la lea el founder** |
| versión | palabras clave | **decisión suya**, no es traducción |
| versión | novedades | listo abajo |
| versión | URL de soporte | la misma |
| versión | **7 capturas propias** | se reutilizan los mismos ficheros del español |

---

## ⚠️ DOS COSAS DESACTUALIZADAS EN LA FICHA, EN LOS TRES IDIOMAS

Detectadas al leer la descripción española para traducirla. **No se han tocado**
—el copy público lo escribe el founder— pero la traducción las arrastraría:

| dice la ficha | decisión vigente |
|---|---|
| *"Los análisis se pagan con **tokens** (compras dentro de la app)"* | **1-sep-2026**: al usuario solo se le habla de **créditos**. "Token" no existe de cara afuera. |
| *"«Professional» es una **suscripción anual** que desbloquea los módulos avanzados"* | **3-sep-2026**: se acabó la membresía anual de 19,99 €. El acceso profesional lo da una suscripción **Medio o superior**. |

Si el founder lo confirma, se corrigen en es, en e it a la vez.

---

## NOMBRE Y SUBTÍTULO

    nome:      The Dogs' Mind
    sottotitolo:  Il problema non è il tuo cane

(El subtítulo español es *"Tu perro no es el problema"*. La forma italiana
natural invierte el orden; dice lo mismo.)

---

## DESCRIPCIÓN — traducción fiel de la aprobada

The Dogs' Mind è un'intelligenza artificiale specializzata in comportamento canino creata da Teo Mariscal, punto di riferimento internazionale nell'analisi del comportamento animale, curata su centinaia di casi reali e su una bibliografia scientifica selezionata. È un'app pensata sia per medici veterinari esperti in comportamento e per esperti in modificazione comportamentale, sia per i proprietari.

Per il veterinario è lo strumento di supporto nella visita comportamentale: esegue analisi funzionali rigorose in pochi minuti, propone piani di intervento di ottima qualità e mantiene un monitoraggio quotidiano del caso che sarebbe molto difficile sostenere a mano. Tiene il registro di ogni paziente, l'evoluzione del caso e la comunicazione con il cliente, tutto in un unico posto. Ti permette di fare un passo in più e di ottimizzare il tuo tempo senza rinunciare al rigore.

E non solo per i professionisti: se sei proprietario di un cane, mette quello stesso rigore alla tua portata. Ti spiega che cosa cerca di ottenere il tuo cane con il suo comportamento, con un'analisi funzionale chiara e accessibile, e ti aiuta a risolverlo consegnandoti un piano di intervento passo dopo passo basato su metodi rispettosi da applicare a casa; e ti accompagna con un monitoraggio quotidiano che ti guida ogni giorno e registra l'evoluzione, perché tu veda i progressi reali del tuo cane.

È un grande alleato per il professionista nella versione Professional e un aiuto enormemente prezioso per i privati nella versione Pet Owner.

Accanto allo strumento di modificazione del comportamento trovi una sezione di educazione e addestramento con una precisione tecnica sorprendente e degli "Aigents" che saranno ottimi consiglieri su altri aspetti della vita quotidiana con il tuo cane.

Il modo migliore per verificarlo è provarla: entra in Home, apri Nuova consulenza, inserisci i tuoi casi e scopri il suo potenziale. Le risposte si appoggiano su letteratura scientifica di analisi del comportamento e su centinaia di casi di successo con cui è stato alimentato il cervello di questa intelligenza artificiale.

Approccio etico LIMA (Least Intrusive, Minimally Aversive). Non usiamo né consigliamo metodi avversivi.

IMPORTANTE The Dogs' Mind è uno strumento di supporto e non sostituisce la valutazione in presenza di un veterinario o di un professionista del comportamento, soprattutto in caso di problemi di salute o di comportamenti di aggressività.

PRIVACY Il testo che scrivi sul tuo cane viene elaborato con IA (Anthropic / Claude) per generare l'analisi, con il tuo consenso esplicito. Informativa sulla privacy: https://thedogsmind.net/privacy.html

ACQUISTI Le analisi si pagano con crediti (acquisti in app). "Professional" è un abbonamento che sblocca i moduli avanzati.

> NOTA: en el último párrafo se ha escrito **crediti** y se ha quitado
> **"annuale"**, para no publicar en italiano lo que ya no es cierto. Si el
> founder prefiere traducir literalmente la ficha española tal como está, se
> cambia. Lo que no se puede es que el italiano diga una cosa y la app haga
> otra.

---

## PALABRAS CLAVE — las decide el founder

Las españolas son:

    reactivo,agresivo,desobediente,escapista,miedo,fobia,ansiedad,separacion,adiestramiento,conducta

Equivalente italiano propuesto (100 caracteres máx., sin espacios tras las comas):

    reattivo,aggressivo,disobbediente,fuga,paura,fobia,ansia,separazione,addestramento,comportamento

No es una traducción: es posicionamiento. El founder decide.

---

## NOVEDADES (1.0.39)

Pendiente: se escriben cuando se sepa qué lleva la 1.0.39.
Las de la 1.0.38 en italiano ya están escritas y se usaron en Google Play.

---

## CÓMO SE APLICA, cuando la 1.0.38 esté aprobada

1. `POST /v1/appInfoLocalizations` con `locale: "it"` sobre el appInfo editable.
2. `POST /v1/appStoreVersionLocalizations` con `locale: "it"` sobre la 1.0.39.
3. Subir las 7 capturas: se reutilizan los mismos ficheros del español
   (`appScreenshotSets` → `appScreenshots`, reservar + subir + commit).
4. Enviar a revisión.
