#!/usr/bin/env python3
"""Auditor — revisa un repositorio ANTES de instalarlo.

Lee. Nunca ejecuta.

Uso:
    python auditor.py https://github.com/usuario/proyecto
    python auditor.py ./carpeta-local
    python auditor.py https://github.com/usuario/proyecto --detalle

No necesita instalar nada: solo Python 3.10 o mas nuevo, y git si le pasas una
direccion de GitHub.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# 🔴 En Windows la consola es cp1252 y Python se cae al imprimir el semáforo
# (UnicodeEncodeError con 🟢🟡🔴). Pasaba DESPUÉS de leer los 751 archivos: hacía
# todo el trabajo y tronaba en la última línea, justo al dar el veredicto.
# Se reconfigura la salida a UTF-8; si la terminal no lo soporta, se sigue igual.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8")
    except Exception:
        pass

VERSION = "1.0.1"

IGNORAR_DIR = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", "target", "vendor", ".idea", ".vscode", "site-packages",
}

# Carpetas de prueba: su contenido es de mentira A PROPOSITO. Se leen y se
# cuentan, pero NO pesan en el semaforo. Sin esto el auditor grita lobo en
# cualquier proyecto serio, y un auditor que grita lobo no sirve de nada.
DIR_PRUEBAS = {
    "tests", "test", "e2e", "smoke", "spec", "__tests__", "fixtures",
    "testdata", "examples", "example", "mocks", "__mocks__",
}

# Texto que delata que una "credencial" es de relleno
FALSAS = re.compile(
    r"your|xxx|must[-_ ]never|example|sample|fake|dummy|placeholder|redact"
    r"|<[^>]*>|\.\.\.|changeme|replace|abc123|1234567890|\btest\b|foo|bar",
    re.I,
)

EXTENSIONES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".bash", ".zsh", ".ps1", ".bat",
    ".cmd", ".rb", ".go", ".rs", ".php", ".json", ".yml", ".yaml", ".toml",
    ".cfg", ".ini", ".env", ".md", ".txt", ".mjs", ".cjs",
}
NOMBRES_EXTRA = {"Dockerfile", "Makefile", "package.json", ".env.example"}
MAX_BYTES = 2_000_000


@dataclass
class Senal:
    clave: str
    titulo: str
    riesgo: str  # "alto" | "medio" | "info"
    explicacion: str
    que_hacer: str
    hallazgos: list[tuple[str, int, str]] = field(default_factory=list)


REGLAS: list[tuple[str, str, str, str, str, str]] = [
    (
        "tuberia",
        r"(?:curl|wget)\s[^\n|]*\|\s*(?:sudo\s+)?(?:ba)?sh"
        r"|i(?:rm|wr)\s[^\n|]*\|\s*iex"
        r"|Invoke-Expression\s*\(\s*(?:irm|iwr|Invoke-)",
        "Se instala descargando y ejecutando sin leer",
        "medio",
        "El instalador baja un archivo de internet y lo ejecuta de inmediato. "
        "Estas confiando en lo que haya en esa direccion EN ESE MOMENTO. Es un "
        "patron comun (Homebrew y otros lo usan) y no prueba mala intencion, "
        "pero si ese archivo cambia, cambia lo que corre en tu maquina.",
        "Baja el instalador a un archivo y leelo antes de correrlo.",
    ),
    (
        "hooks",
        r'"(?:pre|post)install"\s*:',
        "Corre comandos solo con instalarlo",
        "alto",
        "Los ganchos preinstall/postinstall de npm se ejecutan con solo "
        "instalar el paquete, antes de que uses nada.",
        "Mira que comando corre ese gancho. Si no lo entiendes, no lo instales.",
    ),
    (
        "red_abierta",
        r"""(?:host|HOST|bind|listen)\s*[=:]\s*["']?0\.0\.0\.0"""
        r"""|["']0\.0\.0\.0["']\s*(?:,|\)|$)"""
        r"""|--host[= ]0\.0\.0\.0""",
        "Escucha en TODA la red, no solo en tu maquina",
        "medio",
        "0.0.0.0 significa que acepta conexiones de cualquiera que alcance tu "
        "equipo. En tu casa detras del router, riesgo bajo. En el wifi de un "
        "cafe o un coworking, cualquiera en esa red puede tocarlo.",
        "Busca una variable HOST y ponla en 127.0.0.1.",
    ),
    (
        "auth_apagada",
        r"\b[A-Za-z_]*auth[A-Za-z_]*(?:enabled|required|_on|_needed)\s*[=:]\s*"
        r"(?:False|false|0|no|off)\b"
        r"|\b(?:require|enable|use)[_A-Za-z]*auth\w*\s*[=:]\s*"
        r"(?:False|false|0|no|off)\b",
        "Trae la autenticacion APAGADA de fabrica",
        "medio",
        "Viene sin contrasena por defecto. Por si solo no es grave: un programa "
        "que solo escucha en TU maquina no necesita contrasena. Se vuelve grave "
        "si ademas escucha en toda la red (ver abajo).",
        "Enciendela antes de usarlo, y cambia cualquier token por defecto.",
    ),
    (
        "ofuscacion",
        r"(?:b64decode|atob|FromBase64String|base64\.decode)"
        r"[^\n]{0,120}(?:\bexec\b|\beval\b|Invoke-Expression|\biex\b)",
        "Codigo escondido que luego se ejecuta",
        "alto",
        "Texto codificado en base64 que despues se ejecuta. Casi nunca hay una "
        "razon buena para esto: sirve para que no se vea que hace.",
        "NO lo instales sin que alguien que sepa lo revise.",
    ),
    (
        "ejecucion",
        r"(?<![.\w/])(?:eval|exec)\s*\("
        r"|os\.system\s*\("
        r"|shell\s*=\s*True"
        r"|child_process"
        r"|Start-Process",
        "Ejecuta comandos armados sobre la marcha",
        "medio",
        "Construye y corre comandos en el momento. Es normal en herramientas "
        "de desarrollo, pero es por donde entra lo malo cuando algo sale mal.",
        "Revisa de donde sale el texto que ejecuta. Si viene de internet, ojo.",
    ),
    (
        "llave_pegada",
        r"\b(?:sk-[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}"
        r"|xox[baprs]-[A-Za-z0-9\-]{15,})",
        "Hay una credencial de verdad escrita en el codigo",
        "alto",
        "Aparece algo con forma de credencial real dentro de los archivos. O "
        "es una llave filtrada de alguien, o es una llave compartida que "
        "usarias sin saberlo.",
        "No lo uses. Y si la llave es tuya, revocala hoy.",
    ),
    (
        "credenciales",
        r"\b[A-Z][A-Z0-9_]*(?:API_KEY|_TOKEN|_SECRET|PASSWORD|_KEY)\b",
        "Maneja credenciales",
        "info",
        "Pide y guarda llaves de otros servicios. No es malo por si mismo, "
        "pero define que tanto te cuesta si algo sale mal.",
        "Fijate DONDE las guarda y si quedan en texto plano.",
    ),
    (
        "historial",
        r"\b(?:sqlite3|CREATE TABLE|conversation_log|chat_history)\b"
        r"""|["'][\w/\\.\-]+\.db["']""",
        "Guarda un historial en tu disco",
        "info",
        "Crea una base de datos o un registro. Suele ser local y util, pero es "
        "un archivo con tu actividad que quiza no sabias que existe.",
        "Ubica el archivo por si quieres borrarlo.",
    ),
]

RE_URL = re.compile(r"https?://([A-Za-z0-9.\-]+)")
DOMINIOS_NORMALES = {
    "github.com", "raw.githubusercontent.com", "www.github.com", "gitlab.com",
    "api.github.com", "objects.githubusercontent.com",
    "pypi.org", "files.pythonhosted.org", "registry.npmjs.org", "npmjs.com",
    "www.npmjs.com", "docs.python.org", "opensource.org", "www.apache.org",
    "creativecommons.org", "schema.org", "www.w3.org", "json-schema.org",
    "img.shields.io", "shields.io", "localhost", "127.0.0.1", "0.0.0.0",
    "example.com", "www.example.com", "astral.sh", "sh.rustup.rs",
}


def archivos(raiz: Path):
    for p in sorted(raiz.rglob("*")):
        if not p.is_file():
            continue
        if any(parte in IGNORAR_DIR for parte in p.parts):
            continue
        if p.suffix.lower() not in EXTENSIONES and p.name not in NOMBRES_EXTRA:
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        yield p


# Un comentario que HABLA de algo peligroso no HACE nada peligroso. Sin esto,
# cualquier auditor, linter o documentacion que mencione estos patrones se marca
# a si mismo — y nosotros fuimos el primer caso.
RE_COMENTARIO = re.compile(r"""^\s*(#|//|/\*|\*|<!--|--|;|r?["']\s*[|(])""")
RE_ENTRECOMILLADO = re.compile(r"""["'][^"']{1,60}["']""")


def es_mencion(linea: str) -> bool:
    """Comentario, o un patron escrito como texto (una regla, no una accion)."""
    return bool(RE_COMENTARIO.match(linea))


def es_lista(linea: str) -> bool:
    """Una linea con varios textos entrecomillados separados por comas es una
    lista o una lista blanca, no una direccion donde se pone a escuchar."""
    return len(RE_ENTRECOMILLADO.findall(linea)) >= 3


def es_de_prueba(rel_partes: tuple[str, ...], nombre: str) -> bool:
    if any(parte.lower() in DIR_PRUEBAS for parte in rel_partes):
        return True
    n = nombre.lower()
    return n.startswith(("test_", "conftest")) or n.endswith(
        (".test.js", ".test.ts", ".spec.js", ".spec.ts", "_test.py", "_test.go")
    )


def revisar(raiz: Path) -> tuple[list[Senal], dict[str, int], int, int]:
    senales = {c: Senal(c, t, r, e, q) for c, _, t, r, e, q in REGLAS}
    # re.I es necesario: las variables de entorno van en MAYUSCULAS
    # (PROXY_AUTH_ENABLED=false) y las de codigo en minusculas.
    compiladas = [(c, re.compile(p, re.I)) for c, p, *_ in REGLAS]
    dominios: dict[str, int] = defaultdict(int)
    total = 0
    pruebas = 0

    for archivo in archivos(raiz):
        try:
            texto = archivo.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        total += 1
        relp = archivo.relative_to(raiz)
        rel = str(relp).replace("\\", "/")
        prueba = es_de_prueba(relp.parts, archivo.name)
        if prueba:
            pruebas += 1

        if not prueba:
            lineas = texto.split("\n")
            es_md = archivo.suffix.lower() == ".md"
            for clave, patron in compiladas:
                # la documentacion solo cuenta para como se instala
                if es_md and clave != "tuberia":
                    continue
                s = senales[clave]
                for n, linea in enumerate(lineas, 1):
                    if len(s.hallazgos) >= 40:
                        break
                    if len(linea) > 600:
                        linea = linea[:600]
                    if es_mencion(linea):
                        continue
                    if not patron.search(linea):
                        continue
                    if clave == "llave_pegada" and FALSAS.search(linea):
                        continue
                    if clave == "red_abierta" and es_lista(linea):
                        continue
                    s.hallazgos.append((rel, n, linea.strip()[:150]))

        for d in RE_URL.findall(texto):
            d = d.lower()
            if d not in DOMINIOS_NORMALES:
                dominios[d] += 1

    encontradas = [s for s in senales.values() if s.hallazgos]
    encontradas += combinaciones(senales)
    return encontradas, dict(dominios), total, pruebas


# Una senal sola puede ser inocente y dos juntas no. Esto es lo que separa a un
# auditor de un buscador de palabras: sin esto, o grita de mas o se calla de mas.
COMBOS: list[tuple[tuple[str, ...], str, str, str]] = [
    (
        ("red_abierta", "auth_apagada"),
        "Abierto a la red Y sin contrasena, las dos cosas juntas",
        "Por separado ninguna es grave. Juntas significan que, de fabrica, "
        "cualquiera en tu misma red —el wifi de un cafe, un coworking, un "
        "hotel— puede usar este programa como si fuera tuyo. Si maneja tus "
        "llaves de otros servicios, las estaria gastando con tu cuenta.",
        "Antes de usarlo, pon HOST=127.0.0.1 y enciende la autenticacion. "
        "Con eso se apaga este punto.",
    ),
    (
        ("tuberia", "hooks"),
        "Se instala sin leerse Y corre comandos al instalar",
        "El instalador se ejecuta sin que lo veas, y ademas hay ganchos que "
        "corren solos al instalar. Es la combinacion por donde entran los "
        "paquetes envenenados.",
        "Baja el instalador, leelo, e instala con --ignore-scripts.",
    ),
]


def combinaciones(senales: dict[str, Senal]) -> list[Senal]:
    extra = []
    for claves, titulo, expl, que in COMBOS:
        if all(senales[c].hallazgos for c in claves):
            s = Senal("combo", titulo, "alto", expl, que)
            for c in claves:
                s.hallazgos.append(senales[c].hallazgos[0])
            extra.append(s)
    return extra


def semaforo(senales: list[Senal]) -> tuple[str, str]:
    riesgos = {s.riesgo for s in senales}
    if "alto" in riesgos:
        return "🔴", "ROJO"
    if "medio" in riesgos:
        return "🟡", "AMARILLO"
    return "🟢", "VERDE"


def imprime(
    origen: str,
    senales: list[Senal],
    dominios: dict[str, int],
    total: int,
    pruebas: int,
    detalle: bool,
) -> int:
    ico, palabra = semaforo(senales)
    orden = {"alto": 0, "medio": 1, "info": 2}
    senales.sort(key=lambda s: orden[s.riesgo])

    print()
    print("=" * 70)
    print(f"  AUDITORIA EN FRIO  ·  {origen}")
    print(f"  {total} archivos leidos  ·  0 ejecutados")
    if pruebas:
        print(f"  {pruebas} son de carpetas de prueba: se leen, pero no cuentan")
    print("=" * 70)

    if not senales:
        print("\n  No aparecio ninguna de las senales que busca este auditor.\n")

    for s in senales:
        marca = {"alto": "🔴", "medio": "🟡", "info": "ℹ️ "}[s.riesgo]
        print(f"\n{marca} {s.titulo}   ({len(s.hallazgos)} coincidencias)")
        print(f"   {s.explicacion}")
        print(f"   → {s.que_hacer}")
        cuantos = len(s.hallazgos) if detalle else 3
        for rel, n, linea in s.hallazgos[:cuantos]:
            print(f"     {rel}:{n}   {linea}")
        if not detalle and len(s.hallazgos) > 3:
            print(f"     … y {len(s.hallazgos) - 3} mas (corre con --detalle)")

    if dominios:
        print(f"\n🌐 A donde puede mandar informacion  ({len(dominios)} dominios)")
        print("   Ya se descartaron los normales (github, npm, pypi…).")
        tope = 60 if detalle else 12
        for d, n in sorted(dominios.items(), key=lambda x: -x[1])[:tope]:
            print(f"     {n:>4}×  {d}")
        if not detalle and len(dominios) > tope:
            print(f"     … y {len(dominios) - tope} mas (corre con --detalle)")

    print("\n" + "=" * 70)
    print(f"  {ico}  {palabra}")
    print("=" * 70)
    print(
        {
            "🟢": "  No aparecieron senales conocidas. Sigue leyendo lo que te importe.",
            "🟡": "  Se puede usar SABIENDO que estas aceptando. Lee los puntos de arriba.",
            "🔴": "  No lo instales hasta entender los puntos marcados en rojo.",
        }[ico]
    )
    print()
    print("  ⚠️  Esto es una PRIMERA PASADA, no una garantia. Busca senales")
    print("      conocidas en el texto de los archivos. Un proyecto malicioso y")
    print("      bien hecho puede pasar en verde. No sustituye leer el codigo ni")
    print("      probarlo en una maquina aislada.")
    print()
    return {"🟢": 0, "🟡": 1, "🔴": 2}[ico]


def traer(origen: str) -> tuple[Path, Path | None]:
    if not origen.startswith(("http://", "https://", "git@")):
        p = Path(origen).expanduser().resolve()
        if not p.is_dir():
            sys.exit(f"No existe la carpeta: {p}")
        return p, None

    if not shutil.which("git"):
        sys.exit("Para bajar de internet necesitas git instalado.")
    tmp = Path(tempfile.mkdtemp(prefix="auditor-"))
    print(f"Bajando {origen} … (solo se copia, no se ejecuta nada)")
    r = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", origen, str(tmp / "repo")],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(f"No se pudo bajar: {(r.stderr or '').strip()[:200]}")
    return tmp / "repo", tmp


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Revisa un repositorio ANTES de instalarlo. Lee, nunca ejecuta.",
    )
    ap.add_argument("origen", help="direccion de GitHub o carpeta local")
    ap.add_argument(
        "--detalle", action="store_true", help="enseña todas las coincidencias"
    )
    ap.add_argument("--version", action="version", version=f"auditor {VERSION}")
    args = ap.parse_args()

    carpeta, tmp = traer(args.origen)
    try:
        senales, dominios, total, pruebas = revisar(carpeta)
        codigo = imprime(args.origen, senales, dominios, total, pruebas, args.detalle)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(codigo)


if __name__ == "__main__":
    main()
