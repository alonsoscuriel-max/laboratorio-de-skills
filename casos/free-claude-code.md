# Caso · free-claude-code

## 🟡 Amarillo — no es un fraude, pero no es lo que te dijeron

**Revisado el 11 de septiembre de 2026.**
`github.com/Alishahryar1/free-claude-code` · MIT · 54,500 estrellas · 8,700 forks

---

## La promesa que salió a revisar

Un reel con **4,584 interacciones y 3,176 comentarios** decía:

> *«Ya podés usar Claude **completamente gratis para siempre**… una herramienta
> que engaña a Claude Code, le hace creer que está hablando con Claude pero en
> realidad usa modelos gratuitos por atrás, **modelos que tienen la misma calidad
> de respuesta y la misma potencia que Claude**… lo único que cambia es quién
> paga la cuenta, o sea nadie.»*

---

## Qué es en realidad

**Un proxy.** Se pone en medio de Claude Code y Anthropic:

```
ANTHROPIC_BASE_URL = http://localhost:8082
```

Todo lo que Claude Code le mandaría a Anthropic ahora pasa por este programa, que
lo reenvía **al proveedor que elijas** de más de 50: NVIDIA, OpenRouter, Groq,
DeepSeek, Mistral, Gemini, Ollama…

> 🔴 **No es Claude más barato. No es Claude.** Es otro modelo con la ventana de
> Claude Code puesta encima.
>
> El propio repositorio lo dice: *«Independent open-source project. **Not
> affiliated with or endorsed by Anthropic**»*.

---

## Lo que encontramos

### 🟡 «Son dos comandos» — sí, pero instalan diez herramientas

El instalador no instala un proxy. Instala **Codex, Pi, OpenCode, RTK, Hermes
Agent, Grok Build, Muse Code, Cline, Aider y DeepSeek Harness.** Modifica el PATH
de forma permanente e instala paquetes npm globales.

**No pide permisos de administrador**, y **valida sumas de verificación** antes de
correr lo que baja — las dos cosas hablan bien de quien lo escribió.

### 🔴 Escucha en toda la red, y sin contraseña de fábrica

```python
host: NonEmptyString = Field(default="0.0.0.0", validation_alias="HOST")
port: int = Field(default=8082, validation_alias="PORT")
proxy_auth_enabled: bool = Field(default=False, ...)
proxy_auth_token: NonEmptyString = Field(default="freecc", ...)
```

Y en `api/dependencies.py`:

```python
if not settings.proxy_auth_enabled:
    return          # no revisa nada
```

**En tu casa detrás del router: riesgo bajo. En el wifi de un café o un
coworking: cualquiera en esa red puede mandar peticiones por tu proxy** — o sea,
gastar tu cuota con tus llaves.

**Se arregla:** `HOST=127.0.0.1` y encender la autenticación.

### ✅ Pero NO te pueden robar las llaves — y esto hay que decirlo

**Nuestra primera lectura fue que el panel de las llaves quedaba expuesto.
Estábamos equivocados.**

`api/admin_security.py` rechaza cualquier conexión que no venga de la propia
máquina, y además valida las cabeceras `Host` y `Origin`. Se aplica en **las 14
rutas** del panel. **Está bien hecho.**

> 🔑 **Ésta es la diferencia entre revisar y suponer.** La lectura rápida gritaba
> *«te roban las llaves»* — y era falso. **No te las pueden leer, pero sí
> usarlas.** Son cosas distintas.

### ℹ️ Guarda tus conversaciones en tu disco

`runtime/code_sessions_sqlite.py` crea una base de datos con tus prompts y
transcripciones. **Es local; no detectamos que la mande a ningún lado.** Pero es
un archivo con tu actividad que probablemente no sabías que existe.

### 🔴 Tu código sale de tu equipo

Es inherente a lo que hace: **lo que le pides a Claude Code viaja a NVIDIA,
OpenRouter, DeepSeek o quien elijas**, en planes gratuitos donde normalmente se
permite usar tus datos para entrenar.

**Si haces trabajo para clientes, el código de tu cliente se va con él.**

---

## ¿Y la promesa de «la misma calidad»? La probamos

**No instalamos el proxy** *(no teníamos dónde aislarlo de verdad)*. Fuimos
directo a los modelos gratuitos, que es de lo que habla la afirmación.

**La tarea:** limpiar un CSV de ventas con basura real —duplicados, tres formatos
de fecha, `$` con comas y con punto de miles, importes vacíos y en cero— y sacar
un resumen por cliente. **El juez es la computadora:** se ejecuta el programa que
devuelve cada modelo y se compara contra el resultado correcto.

| Modelo | Corrida 1 | Corrida 2 |
|---|---|---|
| `nvidia/nemotron-3-ultra-550b` *(el más grande de los gratis)* | ✅ importes correctos | 🔴 **×100** |
| `google/gemma-4-31b` | ✅ importes correctos | ⚪ sin cuota |
| `cohere/north-mini-code` *(especializado en código)* | 🔴 ni compila | 🔴 $3,350 → **$3.35** |
| `poolside/laguna-s-2.1` | ⚪ nunca respondió | ⚪ nunca respondió |

### El hallazgo: no es que sea malo. Es que es impredecible.

**El mismo modelo, la misma tarea, `temperature 0`, cambiando una frase de la
instrucción:**

```
Corrida 1 → Clínica Dental Sonríe    9,000.75   ✅
Corrida 2 → Clinica Dental Sonrie  563,475.00   🔴
```

**La causa fue una línea:**

```python
s = importe.strip().replace('$','').replace(' ','').replace('.','').replace(',','')
```

Borra todos los puntos y todas las comas. **`$1,250.00` se vuelve `125000`.**

### 🔑 Y lo peor: los programas CORRIERON

**Sin error. Sin alerta.** Generaron un archivo impecable, con los clientes bien
agrupados y bien ordenados, **y los números mal.**

> **Un programa que truena lo encuentras en cinco minutos.**
> **Éste te lo llevas al reporte del mes.**

---

## 🔴 Un error nuestro, para que no se repita

**La primera corrida se tiró completa.** Nuestra instrucción decía *«trata como
el mismo cliente los que solo difieren en mayúsculas/minúsculas»*, pero
*«Taquería»* y *«TAQUERIA»* difieren **también en el acento**.

**Los modelos siguieron la instrucción al pie de la letra. El que la escribió mal
fuimos nosotros.** Se corrigió y se volvió a correr desde cero.

---

## Resumen

| ✅ Se puede afirmar | ❌ No se puede afirmar |
|---|---|
| **No es Claude** | «Es un fraude» — es un proyecto real, MIT, con 54.5k estrellas |
| **Abre el puerto 8082 a toda la red sin contraseña de fábrica** | «Te roban las llaves» — el panel es solo local, y está bien hecho |
| **Tu código sale a un tercero** | «Los modelos gratis son basura» — dos dieron el resultado correcto |
| **Instala ~10 herramientas, no un proxy** | |
| **Y cuando falla, falla callado** | |

**Si lo vas a usar de todos modos:** pon `HOST=127.0.0.1`, enciende la
autenticación, y **nunca lo uses con código de un cliente.**
