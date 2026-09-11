# 🔬 Laboratorio

**Revisa lo que vas a instalar, antes de instalarlo.**

Cada semana sale un video que te promete que con dos comandos vas a tener algo
increíble gratis. A veces es cierto. **El problema es que no hay manera de
saberlo antes de correrlo** — y para cuando te enteras, ya corrió.

Esto es lo que usamos nosotros antes de probar cualquier cosa. **Lee. Nunca
ejecuta.**

```bash
python auditor.py https://github.com/usuario/proyecto
```

Y te contesta con un semáforo:

```
🟢 VERDE     No apareció ninguna de las señales conocidas.
🟡 AMARILLO  Se puede usar sabiendo qué estás aceptando.
🔴 ROJO      No lo instales hasta entender los puntos marcados.
```

---

## Para qué sirve de verdad

**No te dice «esto es seguro».** Nadie puede decirte eso.

Te dice **qué estás aceptando**, en español, antes de que sea tarde:

- **¿Se instala bajando un archivo y ejecutándolo sin que lo veas?**
- **¿Corre comandos con solo instalarse?** *(los ganchos de npm)*
- **¿Abre tu equipo a toda la red, o solo a ti?**
- **¿Trae la contraseña apagada de fábrica?**
- **¿Hay código escondido en base64 que luego se ejecuta?**
- **¿Hay una credencial de verdad escrita en el código?**
- **¿Maneja tus llaves? ¿Guarda un historial en tu disco?**
- **¿A qué dominios puede mandar información?**

### Y sabe combinar, que es lo que lo separa de un buscador de palabras

**Una señal sola puede ser inocente y dos juntas no.**

Un programa que escucha solo en tu máquina **no necesita contraseña.** Uno que
escucha en toda la red **y** viene sin contraseña significa que, de fábrica,
cualquiera en el wifi del café puede usarlo como si fuera tuyo.

**El auditor marca esa combinación en rojo y te dice la línea que la arregla.**
Por eso no pinta todo de rojo: `psf/requests` sale 🟢 verde.

---

## Cómo se usa

**Necesitas Python 3.10 o más nuevo.** Nada más. *(Y `git`, si le pasas una
dirección de GitHub.)*

```bash
# baja el auditor
git clone https://github.com/TU-USUARIO/laboratorio
cd laboratorio

# revisa cualquier repositorio
python auditor.py https://github.com/usuario/proyecto

# o una carpeta que ya tengas
python auditor.py ./carpeta

# todas las coincidencias, no solo las tres primeras
python auditor.py https://github.com/usuario/proyecto --detalle
```

**Devuelve 0 si es verde, 1 si es amarillo y 2 si es rojo**, por si lo quieres
usar dentro de otro proceso.

---

## ⚠️ Lo que NO es

**Esto es una primera pasada, no una garantía.** Busca señales conocidas en el
texto de los archivos.

🔴 **Un proyecto malicioso y bien hecho puede pasar en verde.** Verde significa
*«no apareció nada de lo que sé buscar»*, no *«es seguro»*.

**No sustituye leer el código de lo que te importa, ni probarlo en una máquina
aislada.** Sirve para lo de antes: para saber dónde mirar, y para decidir si
vale la pena mirar.

---

## El protocolo completo

El auditor es **el paso 2**. Así revisamos nosotros:

| | | |
|---|---|---|
| **1** | **Ingreso** | De dónde viene, quién lo hizo, qué promete exactamente |
| **2** | **Auditoría en frío** | **Leer sin ejecutar nada.** Aquí entra `auditor.py` |
| **3** | **Prueba aislada** | Correrlo **con datos inventados y sin una sola llave real** |
| **4** | **Veredicto** | Qué hace bien, qué hace mal, y si la promesa era cierta |
| **5** | **Destino** | Se adopta, se adapta, o se descarta — y se escribe por qué |

> 🔑 **El orden no es decorativo.** El paso 2 va antes que el 3 **siempre**. Y si
> no tienes dónde aislarlo de verdad *(una máquina virtual, un contenedor, una
> máquina desechable)*, **el paso 3 no se hace.** Una carpeta aparte no aísla
> nada: un programa que corre comandos llega a donde llegues tú.
>
> **La defensa no es la carpeta. Es leer antes de correr.**

---

## Casos revisados

| Proyecto | El auditor | Después de leerlo completo | |
|---|---|---|---|
| [free-claude-code](casos/free-claude-code.md) | 🔴 | 🟡 **Amarillo** | *«Usa Claude gratis para siempre»* — no es un fraude, pero **no es Claude** |

### 🔑 Y fíjate en esas dos columnas, porque ahí está todo

**El auditor lo marca 🔴** por una combinación real: escucha en toda la red **y**
viene sin contraseña.

**Al leer el código completo baja a 🟡**, por dos razones que una máquina no podía
saber: **el panel donde viven las llaves sí está protegido** *(solo acepta
conexiones de tu propia máquina, y está bien hecho)*, y **lo demás se arregla con
una línea** *(`HOST=127.0.0.1`)*.

> **Ese salto de 🔴 a 🟡, con razones, es exactamente para lo que existen los
> pasos 3 y 4.** El auditor te dice dónde mirar. **No te dice el veredicto.**

**Cada caso trae lo que encontramos, cómo lo comprobamos, y también lo que
resultó ser falso de nuestras propias sospechas.**

---

## Por qué está publicado

Lo hicimos para nosotros y lo dejamos abierto **porque el problema es de todos**:
nadie tiene tiempo de leer cada repositorio que le recomiendan, y las
recomendaciones llegan más rápido de lo que se pueden revisar.

**Si le agregas una señal que nos falta, mándala.** Y si el auditor marca en rojo
algo que está bien, **eso también queremos saberlo** — un auditor que exagera es
tan inútil como uno que se queda callado.

---

## Licencia

MIT. Úsalo, cámbialo, cóbralo si quieres.

**Hecho por [Laboratorio Digital](https://instagram.com/laboratoriodigital).**
