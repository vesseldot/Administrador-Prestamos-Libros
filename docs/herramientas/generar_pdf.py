"""Genera los PDF de la documentación a partir de los archivos Markdown de docs/.

Uso:
    python docs/herramientas/generar_pdf.py                  # los tres documentos
    python docs/herramientas/generar_pdf.py guia_estudio     # solo uno
    python docs/herramientas/generar_pdf.py --conservar-html # deja el HTML intermedio para revisarlo

Proceso: pandoc convierte cada Markdown en HTML; Google Chrome o Microsoft Edge (sin ventana)
dibuja los diagramas Mermaid y genera el PDF con encabezados, pies y números de página; pypdf
une la portada y el cuerpo. El índice se calcula en dos pasadas para conocer el número de página
de cada capítulo. Requisitos: docs/herramientas/LEEME.md.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.parse
import urllib.request
import uuid
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs"
REPOSITORIO = "https://github.com/vesseldot/Administrador-Prestamos-Libros/blob/develop/"
PROYECTO = "Administrador de Préstamos de Libros"
AUTORIA = "© 2026 Vessel-dot · Licencia MIT"

MERMAID_VERSION = "11.4.1"
MERMAID_URL = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
MERMAID_SHA256 = "a43bc1afd446f9c4cc66ac5dd45d02e8d65e26fc5344ec0ef787f88d6ddb6f9e"
CACHE = Path(tempfile.gettempdir()) / "biblioteca-docs"
ESCALA_MINIMA = 0.6
ANCHO_MENSAJE = 24

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]

NAVEGADORES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

DOCUMENTOS = {
    "guia_tecnica": {
        "salida": "GUIA_TECNICA_COLABORADORES.pdf",
        "titulo": "Guía técnica para colaboradores",
        "subtitulo": "Manual de referencia del sistema, con anexos de arquitectura, flujos, modelo semántico, "
                     "seguridad, integración, instalación, contribución y mantenimiento",
        "partes": [("GUIA_TECNICA_COLABORADORES.md", None), ("ARQUITECTURA.md", "A"), ("FLUJOS_DATOS.md", "B"),
                   ("MODELO_SEMANTICO.md", "C"), ("SEGURIDAD.md", "D"), ("../INTEGRACION.md", "E"),
                   ("INSTALACION.md", "F"), ("CONTRIBUCION.md", "G"), ("MANTENIMIENTO.md", "H")],
    },
    "guia_estudio": {
        "salida": "GUIA_ESTUDIO_PROYECTO.pdf",
        "titulo": "Guía de estudio del proyecto",
        "subtitulo": "Cómo funciona por dentro y cómo defenderlo: fundamentos, código real, preguntas de "
                     "defensa y ejercicios resueltos",
        "partes": [("GUIA_ESTUDIO_PROYECTO.md", None)],
    },
    "informe": {
        "salida": "INFORME_LIMPIEZA_Y_DOCUMENTACION.pdf",
        "titulo": "Informe de limpieza y documentación",
        "subtitulo": "Revisión del código, cambios de legibilidad, documentación generada y verificación",
        "partes": [("INFORME_LIMPIEZA_Y_DOCUMENTACION.md", None)],
    },
}

ESTILOS = """
:root { --primario:#1f4e79; --acento:#2e75b6; --texto:#1f2933; --suave:#5b6775; --borde:#d5dbe3;
        --fondo:#f4f6f9; --mono:"Cascadia Mono", Consolas, "Courier New", monospace; }
html { -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body { font-family:"Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size:10pt; line-height:1.5;
       color:var(--texto); margin:0; background:#fff; }
h1, h2, h3, h4 { color:var(--primario); line-height:1.25; break-after:avoid; position:relative; }
h1 { font-size:20pt; border-bottom:2pt solid var(--acento); padding-bottom:4pt; margin:0 0 12pt; }
h2 { font-size:14.5pt; margin:18pt 0 8pt; }
h3 { font-size:12pt; margin:14pt 0 6pt; }
h4 { font-size:10.5pt; margin:12pt 0 4pt; }
.capitulo { break-before:page; margin-top:0; }
h2.capitulo { font-size:18pt; border-bottom:1.5pt solid var(--acento); padding-bottom:4pt; }
p { margin:0 0 7pt; orphans:3; widows:3; }
a { color:var(--acento); text-decoration:none; }
strong { font-weight:600; }
code { font-family:var(--mono); font-size:8.6pt; background:#eef1f5; padding:0.5pt 2.5pt; border-radius:2pt;
       overflow-wrap:anywhere; }
div.sourceCode, pre { margin:6pt 0 10pt; }
pre { font-family:var(--mono); font-size:8.2pt; line-height:1.42; background:#f6f8fa;
      border:0.75pt solid var(--borde); border-left:3pt solid var(--acento); border-radius:3pt; padding:7pt 9pt;
      white-space:pre-wrap !important; overflow-wrap:anywhere; break-inside:avoid; }
div.sourceCode pre { margin:0; }
pre code, pre > code.sourceCode { background:none; padding:0; font-size:inherit; white-space:pre-wrap !important; }
pre > code.sourceCode > span { display:inline; }
table { border-collapse:collapse; width:100%; margin:6pt 0 12pt; font-size:8.7pt; line-height:1.38; }
thead { display:table-header-group; }
tr { break-inside:avoid; }
th { background:var(--primario); color:#fff; text-align:left; font-weight:600; padding:4pt 6pt;
     vertical-align:bottom; }
td { border-bottom:0.6pt solid var(--borde); padding:3.5pt 6pt; vertical-align:top; overflow-wrap:break-word; }
tbody tr:nth-child(even) td { background:#f7f9fb; }
td code, th code { font-size:8pt; overflow-wrap:break-word; }
th code { background:rgba(255,255,255,0.16); color:#fff; }
blockquote { margin:8pt 0 12pt; padding:7pt 11pt; border-left:3pt solid #9aa5b1; background:var(--fondo);
             border-radius:3pt; break-inside:avoid; }
blockquote.nota { border-left-color:#2e75b6; background:#eaf2fb; }
blockquote.aviso { border-left-color:#c27c0e; background:#fdf4e3; }
blockquote p:last-child { margin-bottom:0; }
ul, ol { margin:0 0 8pt; padding-left:18pt; }
li { margin:2pt 0; }
li > p { margin-bottom:3pt; }
ul.task-list { list-style:none; padding-left:4pt; }
ul.task-list input { margin:0 6pt 0 0; vertical-align:middle; }
hr { display:none; }
.diagrama { text-align:center; margin:10pt 0 14pt; break-inside:avoid; }
p:has(+ .diagrama), p:has(+ .solucion) { break-after:avoid; }
.diagrama svg { max-width:100%; height:auto; max-height:8.1in; }
.solucion { border:0.75pt solid #9fd3b0; background:#f0faf3; border-radius:3pt; padding:7pt 11pt;
            margin:4pt 0 12pt; break-inside:avoid; }
.solucion-titulo { font-weight:600; color:#1e7a3c; margin-bottom:4pt; }
.solucion pre { background:#fff; }
.marca { position:absolute; left:0; top:0; font-size:3pt; line-height:1; color:#fff; white-space:nowrap; }
nav.indice { break-after:page; }
nav.indice h1 { margin-bottom:14pt; }
nav.indice ol { list-style:none; padding:0; margin:0; }
nav.indice li { margin:0; }
nav.indice a { display:flex; align-items:baseline; color:var(--texto); }
nav.indice .n1 { font-weight:600; margin-top:5pt; color:var(--primario); }
nav.indice .n1 a { color:var(--primario); }
nav.indice .n2 { padding-left:16pt; font-size:9.3pt; }
nav.indice .t { flex:0 1 auto; }
nav.indice .relleno { flex:1 1 auto; border-bottom:0.8pt dotted #a0aab4; margin:0 4pt; min-width:12pt;
                      transform:translateY(-3pt); }
nav.indice .p { flex:0 0 3em; text-align:right; font-variant-numeric:tabular-nums; }
"""

ESTILOS_PORTADA = """
@page { margin:0; }
html, body { margin:0; padding:0; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body { font-family:"Segoe UI", "Helvetica Neue", Arial, sans-serif; color:#1f2933; }
.portada { width:8.5in; height:10.95in; position:relative; overflow:hidden; }
.banda { background:#1f4e79; color:#fff; padding:1.55in 0.9in 0.75in; }
.proyecto { letter-spacing:2.5pt; font-size:10pt; font-weight:600; color:#bcd6f0; text-transform:uppercase; }
.banda h1 { font-size:32pt; line-height:1.15; margin:14pt 0 12pt; font-weight:700; }
.banda p { font-size:12.5pt; line-height:1.45; margin:0; color:#e3eef9; max-width:6.2in; }
.acento { height:6pt; background:#2e75b6; }
.datos { padding:0.6in 0.9in 0; }
.datos table { border-collapse:collapse; font-size:10pt; width:100%; }
.datos td { padding:6pt 0; border-bottom:0.6pt solid #d5dbe3; vertical-align:top; }
.datos td:first-child { width:1.9in; color:#5b6775; font-weight:600; }
.pie { position:absolute; bottom:0.7in; left:0.9in; right:0.9in; font-size:9pt; color:#5b6775;
       border-top:0.6pt solid #d5dbe3; padding-top:8pt; display:flex; justify-content:space-between; }
"""

SCRIPT_DIAGRAMAS = """
<script src="mermaid.min.js"></script>
<script>
const FUENTES = __FUENTES__;
mermaid.initialize({startOnLoad:false, theme:"neutral", securityLevel:"strict",
                    fontFamily:'"Segoe UI", Arial, sans-serif',
                    flowchart:{useMaxWidth:true, htmlLabels:true, nodeSpacing:28, rankSpacing:34, padding:8},
                    sequence:{useMaxWidth:true, mirrorActors:false, wrap:false, width:130, actorMargin:24,
                              boxMargin:6, messageMargin:24, noteMargin:6, diagramMarginX:8, diagramMarginY:6},
                    er:{useMaxWidth:true}, gitGraph:{useMaxWidth:true}});
(async () => {
  try {
    for (const nodo of document.querySelectorAll(".diagrama")) {
      const indice = Number(nodo.dataset.indice);
      const {svg} = await mermaid.render("diagrama" + indice, FUENTES[indice]);
      nodo.innerHTML = svg;
    }
    await document.fonts.ready;
    window.__escalas = [...document.querySelectorAll(".diagrama svg")].map(svg => {
      const caja = svg.viewBox.baseVal;
      const marco = svg.getBoundingClientRect();
      return {indice: Number(svg.parentElement.dataset.indice),
              escala: caja && caja.width ? Math.min(marco.width / caja.width, marco.height / caja.height) : 1};
    });
    window.__listo = true;
  } catch (error) {
    window.__error = String(error && error.message || error);
    window.__listo = true;
  }
})();
</script>
"""


def fecha_larga(dia: date) -> str:
    return f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def texto_plano(fragmento: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragmento)).strip()


def obtener_mermaid() -> Path:
    destino = CACHE / f"mermaid-{MERMAID_VERSION}.min.js"
    if not destino.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"Descargando mermaid {MERMAID_VERSION}...")
        with urllib.request.urlopen(MERMAID_URL, timeout=60) as respuesta:
            datos = respuesta.read()
        temporal = destino.with_suffix(".tmp")
        temporal.write_bytes(datos)
        temporal.replace(destino)
    huella = hashlib.sha256(destino.read_bytes()).hexdigest()
    if huella != MERMAID_SHA256:
        destino.unlink(missing_ok=True)
        raise SystemExit(f"La copia de mermaid no coincide con la huella esperada ({huella}).")
    return destino


def buscar_navegador() -> Path:
    for ruta in NAVEGADORES:
        if ruta.exists():
            return ruta
    for nombre in ("chrome", "google-chrome", "chromium", "msedge"):
        encontrado = shutil.which(nombre)
        if encontrado:
            return Path(encontrado)
    raise SystemExit("No se encontró Google Chrome ni Microsoft Edge.")


class Navegador:
    """Chrome o Edge sin ventana, controlado por el protocolo DevTools."""

    def __init__(self):
        import websocket
        self.perfil = Path(tempfile.mkdtemp(prefix="biblioteca-pdf-"))
        self.proceso = subprocess.Popen(
            [str(buscar_navegador()), "--headless=new", "--disable-gpu", "--no-first-run",
             "--no-default-browser-check", "--disable-extensions", "--remote-debugging-port=0",
             f"--user-data-dir={self.perfil}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        archivo = self.perfil / "DevToolsActivePort"
        limite = time.time() + 30
        lineas: list[str] = []
        while time.time() < limite:
            try:
                lineas = archivo.read_text().splitlines()
            except OSError:
                lineas = []
            if len(lineas) >= 2:
                break
            time.sleep(0.1)
        else:
            self.cerrar()
            raise SystemExit("El navegador no abrió el puerto de depuración.")
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with abridor.open(f"http://127.0.0.1:{lineas[0]}/json/list", timeout=10) as respuesta:
            objetivos = json.load(respuesta)
        pagina = next(o for o in objetivos if o.get("type") == "page")
        self.ws = websocket.create_connection(pagina["webSocketDebuggerUrl"], suppress_origin=True, timeout=180)
        self._id = 0
        self.escalas: list[dict] = []

    def llamar(self, metodo: str, **parametros):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": metodo, "params": parametros}))
        while True:
            mensaje = json.loads(self.ws.recv())
            if mensaje.get("id") == self._id:
                if "error" in mensaje:
                    raise RuntimeError(f"{metodo}: {mensaje['error']}")
                return mensaje.get("result", {})

    def imprimir(self, ruta: Path, ficha: str, opciones: dict) -> bytes:
        self.llamar("Page.navigate", url=ruta.as_uri())
        expresion = f"window.__ficha === '{ficha}' && window.__listo === true ? (window.__error || 'ok') : ''"
        limite = time.time() + 180
        while True:
            valor = self.llamar("Runtime.evaluate", expression=expresion, returnByValue=True)["result"].get("value")
            if valor:
                break
            if time.time() > limite:
                raise TimeoutError(f"La página {ruta.name} no terminó de cargar.")
            time.sleep(0.2)
        if valor != "ok":
            raise RuntimeError(f"No se pudo dibujar un diagrama de {ruta.name}: {valor}")
        self.escalas = self.llamar("Runtime.evaluate", expression="window.__escalas || []",
                                   returnByValue=True)["result"].get("value") or []
        return base64.b64decode(self.llamar("Page.printToPDF", **opciones)["data"])

    def cerrar(self):
        try:
            self.llamar("Browser.close")
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proceso.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proceso.kill()
        for _ in range(10):
            try:
                shutil.rmtree(self.perfil)
                break
            except OSError:
                time.sleep(0.5)


def partir_mensajes(fuente: str, ancho: int = ANCHO_MENSAJE) -> str:
    """Parte en varias líneas los mensajes y notas largos de un diagrama de secuencia.

    Solo corta en los espacios, para no partir identificadores de código.
    """
    if not fuente.lstrip().startswith("sequenceDiagram"):
        return fuente
    lineas = []
    for linea in fuente.splitlines():
        coincidencia = re.match(r"^(\s*(?:\S+?(?:-{1,2}>>|-{1,2}\)|-{1,2}x)[+-]?\S+?|Note [^:]+):\s*)(.+)$", linea)
        if coincidencia and len(coincidencia.group(2)) > ancho and "<br" not in coincidencia.group(2):
            partes = textwrap.wrap(coincidencia.group(2), ancho, break_long_words=False, break_on_hyphens=False)
            linea = coincidencia.group(1) + "<br/>".join(partes)
        lineas.append(linea)
    return "\n".join(lineas)


def preparar_markdown(texto: str, anexo: str | None, fuentes: list[str]) -> str:
    """Adapta el Markdown para el PDF: diagramas, soluciones desplegables y título."""
    def diagrama(coincidencia):
        fuentes.append(partir_mensajes(coincidencia.group(1).strip()))
        return f'\n<div class="diagrama" data-indice="{len(fuentes) - 1}"></div>\n'

    texto = re.sub(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", diagrama, texto, flags=re.M | re.S)
    texto = re.sub(r"<details>\s*<summary>(.*?)</summary>",
                   r'<div class="solucion"><p class="solucion-titulo">\1</p>', texto)
    texto = texto.replace("</details>", "</div>")
    lineas = texto.splitlines()
    inicio = next(i for i, linea in enumerate(lineas) if linea.startswith("# "))
    if anexo:
        lineas[inicio] = f"# Anexo {anexo}. {lineas[inicio][2:].strip()}"
    else:
        del lineas[inicio]
        siguiente = inicio
        while siguiente < len(lineas) and not lineas[siguiente].strip():
            siguiente += 1
        if siguiente < len(lineas) and lineas[siguiente].startswith("**"):
            del lineas[siguiente]
    return "\n".join(lineas) + "\n"


def convertir(texto: str) -> str:
    resultado = subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "html5", "--wrap=none", "--syntax-highlighting=tango"],
        input=texto, capture_output=True, text=True, encoding="utf-8", check=True)
    return resultado.stdout


def estilos_resaltado() -> str:
    with tempfile.TemporaryDirectory() as carpeta:
        plantilla = Path(carpeta) / "plantilla.html"
        plantilla.write_text("$highlighting-css$", encoding="utf-8")
        resultado = subprocess.run(
            ["pandoc", "-f", "gfm", "-t", "html5", "-s", f"--template={plantilla}", "--syntax-highlighting=tango",
             "--metadata", "title=x"], input="```python\nx = 1\n```\n", capture_output=True, text=True,
            encoding="utf-8", check=True)
    return resultado.stdout


def reescribir_enlaces(fragmento: str, origen: Path, prefijos: dict[Path, str], prefijo_propio: str) -> str:
    def cambiar(coincidencia):
        href = html.unescape(coincidencia.group(1))
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href):
            return coincidencia.group(0)
        if href.startswith("#"):
            return f'href="#{prefijo_propio}{href[1:]}"'
        ruta, _, ancla = href.partition("#")
        ancla = urllib.parse.unquote(ancla)
        destino = (origen.parent / urllib.parse.unquote(ruta)).resolve()
        if destino in prefijos:
            nuevo = f"#{prefijos[destino]}{ancla or 'inicio'}"
        else:
            try:
                relativa = destino.relative_to(RAIZ).as_posix()
            except ValueError:
                return coincidencia.group(0)
            nuevo = REPOSITORIO + relativa + (f"#{ancla}" if ancla else "")
        return f'href="{html.escape(nuevo, quote=True)}"'

    return re.sub(r'href="([^"]*)"', cambiar, fragmento)


def cortes_en_codigo(fragmento: str) -> str:
    """Permite partir el código en línea tras ':', '_', '/', '.' y ',' para que no desborde las tablas."""
    def cortar(coincidencia):
        if coincidencia.group(1):
            return coincidencia.group(1)
        return "<code>" + re.sub(r"([:_/.,])(?=.)", r"\1<wbr>", coincidencia.group(2)) + "</code>"

    return re.sub(r"(<pre\b.*?</pre>)|<code>([^<]*)</code>", cortar, fragmento, flags=re.S)


def ajustar_html(fragmento: str, prefijo: str) -> str:
    fragmento = re.sub(r'<a href="#[^"]*" aria-hidden="true" tabindex="-1"></a>', "", fragmento)
    fragmento = cortes_en_codigo(fragmento)
    fragmento = re.sub(r"<colgroup>.*?</colgroup>", "", fragmento, flags=re.S)
    fragmento = re.sub(r'(<(?:h[1-6]|div|span|a|table|ul|ol|li|section|pre|code)\b[^>]*\bid=")',
                       rf"\1{prefijo}", fragmento)

    def clasificar(coincidencia):
        contenido = coincidencia.group(1)
        inicio = texto_plano(contenido[:200])
        clase = "aviso" if inicio.startswith(("Advertencia", "Importante")) else \
            "nota" if inicio.startswith(("Nota", "Cómo usar", "Consejo")) else ""
        return f'<blockquote class="{clase}">{contenido}</blockquote>' if clase else coincidencia.group(0)

    return re.sub(r"<blockquote>(.*?)</blockquote>", clasificar, fragmento, flags=re.S)


def procesar_encabezados(fragmento: str, principal: bool, entradas: list[dict]) -> str:
    niveles = {2: 1, 3: 2} if principal else {1: 1, 2: 2}

    def marcar(coincidencia):
        etiqueta, atributos, contenido = coincidencia.group(1), coincidencia.group(2), coincidencia.group(3)
        nivel = niveles.get(int(etiqueta[1]))
        identificador = re.search(r'id="([^"]+)"', atributos)
        if nivel is None or identificador is None:
            return coincidencia.group(0)
        numero = len(entradas)
        entradas.append({"id": identificador.group(1), "texto": texto_plano(contenido), "nivel": nivel})
        if nivel == 1:
            atributos += ' class="capitulo"'
        return f'<{etiqueta}{atributos}><span class="marca">§§T{numero}§§</span>{contenido}</{etiqueta}>'

    return re.sub(r"<(h[1-6])((?:\s[^>]*)?)>(.*?)</\1>", marcar, fragmento, flags=re.S)


def indice_html(entradas: list[dict], paginas: dict[int, int] | None) -> str:
    filas = []
    for numero, entrada in enumerate(entradas):
        pagina = str(paginas.get(numero, "")) if paginas else ""
        filas.append(f'<li class="n{entrada["nivel"]}"><a href="#{entrada["id"]}">'
                     f'<span class="t">{html.escape(entrada["texto"])}</span><span class="relleno"></span>'
                     f'<span class="p">{pagina}</span></a></li>')
    return f'<nav class="indice"><h1>Índice</h1><ol>{"".join(filas)}</ol></nav>'


def construir_cuerpo(clave: str) -> tuple[str, list[dict], list[str], list[str]]:
    definicion = DOCUMENTOS[clave]
    rutas = [(DOCS / archivo).resolve() for archivo, _ in definicion["partes"]]
    faltantes = [str(r) for r in rutas if not r.exists()]
    if faltantes:
        raise SystemExit("Faltan archivos: " + ", ".join(faltantes))
    prefijos = {ruta: ("principal-" if anexo is None else f"anexo-{anexo.lower()}-")
                for ruta, (_, anexo) in zip(rutas, definicion["partes"])}
    fuentes: list[str] = []
    entradas: list[dict] = []
    secciones = []
    for ruta, (_, anexo) in zip(rutas, definicion["partes"]):
        prefijo = prefijos[ruta]
        texto = preparar_markdown(ruta.read_text(encoding="utf-8"), anexo, fuentes)
        fragmento = ajustar_html(convertir(texto), prefijo)
        fragmento = reescribir_enlaces(fragmento, ruta, prefijos, prefijo)
        fragmento = procesar_encabezados(fragmento, anexo is None, entradas)
        secciones.append(f'<section class="parte"><span id="{prefijo}inicio"></span>{fragmento}</section>')
    cuerpo = "\n".join(secciones)
    ids = set(re.findall(r'\bid="([^"]+)"', cuerpo))
    rotos = sorted({ancla for ancla in re.findall(r'href="#([^"]+)"', cuerpo) if ancla not in ids})
    return cuerpo, entradas, fuentes, rotos


def pagina_html(titulo: str, contenido: str, estilos: str, ficha: str, diagramas: list[str] | None) -> str:
    script = ""
    if diagramas:
        fuentes = json.dumps(diagramas, ensure_ascii=False).replace("</", "<\\/")
        script = SCRIPT_DIAGRAMAS.replace("__FUENTES__", fuentes)
    else:
        script = "<script>window.__listo = true;</script>"
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{html.escape(titulo)}</title>'
            f"<style>{estilos}</style></head><body><script>window.__ficha = '{ficha}';</script>"
            f"{contenido}{script}</body></html>")


def portada_html(definicion: dict, hoy: date) -> str:
    fuentes = ", ".join(f"docs/{a}" if not a.startswith("..") else a[3:] for a, _ in definicion["partes"])
    filas = [("Proyecto", PROYECTO),
             ("Tecnologías", "Python · Tkinter · Redis · ChromaDB · Qwen3-Embedding-0.6B"),
             ("Repositorio", "github.com/vesseldot/Administrador-Prestamos-Libros"),
             ("Fecha del documento", fecha_larga(hoy)),
             ("Fuente editable", fuentes),
             ("Licencia", "MIT (código del proyecto). El modelo Qwen3-Embedding-0.6B se rige por Apache-2.0.")]
    tabla = "".join(f"<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>" for a, b in filas)
    return (f'<div class="portada"><div class="banda"><div class="proyecto">{html.escape(PROYECTO)}</div>'
            f'<h1>{html.escape(definicion["titulo"])}</h1><p>{html.escape(definicion["subtitulo"])}</p></div>'
            f'<div class="acento"></div><div class="datos"><table>{tabla}</table></div>'
            f'<div class="pie"><span>Proyecto académico · Bases de Datos NoSQL</span>'
            f'<span>{html.escape(AUTORIA)}</span></div></div>')


def opciones_cuerpo(titulo: str) -> dict:
    letra = "font-family:'Segoe UI',Arial,sans-serif; font-size:7.5pt; color:#6b7280;"
    exterior = 'style="width:100%; box-sizing:border-box; padding:0 0.8in;"'
    cabecera = (f'<div {exterior}><div style="{letra} padding-bottom:3pt; display:flex; '
                f'justify-content:space-between; border-bottom:0.5pt solid #d5dbe3;">'
                f"<span>{html.escape(titulo)}</span><span>{html.escape(PROYECTO)}</span></div></div>")
    pie = (f'<div {exterior}><div style="{letra} padding-top:3pt; display:flex; '
           f'justify-content:space-between; border-top:0.5pt solid #d5dbe3;">'
           f"<span>{html.escape(AUTORIA)}</span>"
           f'<span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span>'
           f"</div></div>")
    return {"paperWidth": 8.5, "paperHeight": 11, "marginTop": 0.9, "marginBottom": 0.85, "marginLeft": 0.8,
            "marginRight": 0.8, "printBackground": True, "displayHeaderFooter": True, "headerTemplate": cabecera,
            "footerTemplate": pie, "generateTaggedPDF": True, "generateDocumentOutline": True}


OPCIONES_PORTADA = {"paperWidth": 8.5, "paperHeight": 11, "marginTop": 0, "marginBottom": 0, "marginLeft": 0,
                    "marginRight": 0, "printBackground": True, "displayHeaderFooter": False,
                    "generateTaggedPDF": True}


def paginas_de_marcas(pdf: bytes) -> dict[int, int]:
    from pypdf import PdfReader
    paginas: dict[int, int] = {}
    for numero, pagina in enumerate(PdfReader(io.BytesIO(pdf)).pages, start=1):
        for marca in re.findall(r"§§T(\d+)§§", pagina.extract_text() or ""):
            paginas.setdefault(int(marca), numero)
    return paginas


def generar(clave: str, navegador: Navegador, mermaid: Path, trabajo: Path, hoy: date) -> Path:
    from pypdf import PdfReader, PdfWriter
    definicion = DOCUMENTOS[clave]
    cuerpo, entradas, fuentes, rotos = construir_cuerpo(clave)
    if rotos:
        print(f"  Aviso: enlaces internos sin destino en {clave}: {', '.join(rotos)}")
    shutil.copyfile(mermaid, trabajo / "mermaid.min.js")
    estilos = ESTILOS + estilos_resaltado()
    opciones = opciones_cuerpo(definicion["titulo"])

    ficha = uuid.uuid4().hex
    ruta = trabajo / f"{clave}_1.html"
    ruta.write_text(pagina_html(definicion["titulo"], indice_html(entradas, None) + cuerpo, estilos, ficha,
                                fuentes), encoding="utf-8")
    primera = navegador.imprimir(ruta, ficha, opciones)
    paginas = paginas_de_marcas(primera)
    sin_pagina = [entradas[n]["texto"] for n in range(len(entradas)) if n not in paginas]
    if sin_pagina:
        print(f"  Aviso: no se localizó la página de: {'; '.join(sin_pagina)}")

    ficha = uuid.uuid4().hex
    cuerpo_final = re.sub(r'<span class="marca">§§T\d+§§</span>', "", cuerpo)
    ruta = trabajo / f"{clave}_2.html"
    ruta.write_text(pagina_html(definicion["titulo"], indice_html(entradas, paginas) + cuerpo_final, estilos,
                                ficha, fuentes), encoding="utf-8")
    final = navegador.imprimir(ruta, ficha, opciones)
    pequenos = [f"#{e['indice'] + 1} ({e['escala']:.0%})" for e in navegador.escalas if e["escala"] < ESCALA_MINIMA]
    if pequenos:
        print(f"  Aviso: diagramas reducidos por debajo del {ESCALA_MINIMA:.0%}: {', '.join(pequenos)}")
    if len(PdfReader(io.BytesIO(final)).pages) != len(PdfReader(io.BytesIO(primera)).pages):
        print("  Aviso: el número de páginas cambió entre pasadas; revisa el índice.")

    ficha = uuid.uuid4().hex
    ruta = trabajo / f"{clave}_portada.html"
    ruta.write_text(pagina_html(definicion["titulo"], portada_html(definicion, hoy), ESTILOS_PORTADA, ficha, None),
                    encoding="utf-8")
    portada = navegador.imprimir(ruta, ficha, OPCIONES_PORTADA)

    escritor = PdfWriter()
    escritor.append(PdfReader(io.BytesIO(portada)), import_outline=False)
    escritor.append(PdfReader(io.BytesIO(final)))
    escritor.add_metadata({"/Title": f'{definicion["titulo"]} · {PROYECTO}', "/Author": "Vessel-dot",
                           "/Subject": definicion["subtitulo"], "/Creator": "docs/herramientas/generar_pdf.py",
                           "/Keywords": "Redis, ChromaDB, Tkinter, embeddings, Qwen3, biblioteca"})
    escritor.page_mode = "/UseOutlines"
    salida = DOCS / definicion["salida"]
    with salida.open("wb") as archivo:
        escritor.write(archivo)
    total = len(PdfReader(salida).pages)
    print(f"  {salida.relative_to(RAIZ)}: {total} páginas, {len(fuentes)} diagramas, "
          f"{len(entradas)} entradas de índice")
    return salida


def main():
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("documentos", nargs="*", metavar="documento",
                            help="guia_tecnica, guia_estudio o informe (por defecto, todos)")
    analizador.add_argument("--conservar-html", action="store_true", help="no borrar el HTML intermedio")
    argumentos = analizador.parse_args()
    desconocidos = [d for d in argumentos.documentos if d not in DOCUMENTOS]
    if desconocidos:
        analizador.error(f"documento desconocido: {', '.join(desconocidos)}. Opciones: {', '.join(DOCUMENTOS)}")
    if shutil.which("pandoc") is None:
        raise SystemExit("No se encontró pandoc: https://pandoc.org/installing.html")
    try:
        import pypdf  # noqa: F401
        import websocket  # noqa: F401
    except ImportError as error:
        raise SystemExit(f"Falta {error.name}: pip install -r docs/herramientas/requisitos.txt") from error

    mermaid = obtener_mermaid()
    trabajo = Path(tempfile.mkdtemp(prefix="biblioteca-html-"))
    hoy = date.today()
    navegador = Navegador()
    try:
        for clave in argumentos.documentos or list(DOCUMENTOS):
            print(f"Generando {clave}...")
            generar(clave, navegador, mermaid, trabajo, hoy)
    finally:
        navegador.cerrar()
        if argumentos.conservar_html:
            print(f"HTML intermedio en {trabajo}")
        else:
            shutil.rmtree(trabajo, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
