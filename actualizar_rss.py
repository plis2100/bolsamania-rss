from __future__ import annotations

import copy
import email.utils
import os
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

FUENTE = "https://www.bolsamania.com/rss/generarRss2.php"
SALIDA = Path("rss.xml")
MAXIMO_NOTICIAS = 1000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/140 Safari/537.36"
)

ET.register_namespace(
    "content",
    "http://purl.org/rss/1.0/modules/content/",
)


def descargar_rss() -> bytes:
    peticion = urllib.request.Request(
        FUENTE,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        contenido = respuesta.read()

    if b"<rss" not in contenido or b"<item>" not in contenido:
        raise RuntimeError("Bolsamanía no devolvió una RSS válida")

    return contenido


def texto(elemento: ET.Element | None, etiqueta: str) -> str:
    if elemento is None:
        return ""

    nodo = elemento.find(etiqueta)
    return (nodo.text or "").strip() if nodo is not None else ""


def identificador(item: ET.Element) -> str:
    return (
        texto(item, "guid")
        or texto(item, "link")
        or texto(item, "title")
    )


def fecha_item(item: ET.Element) -> datetime:
    fecha = texto(item, "pubDate")

    if not fecha:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        resultado = email.utils.parsedate_to_datetime(fecha)

        if resultado.tzinfo is None:
            resultado = resultado.replace(tzinfo=timezone.utc)

        return resultado
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def cargar_historico() -> dict[str, ET.Element]:
    noticias: dict[str, ET.Element] = {}

    if not SALIDA.exists():
        return noticias

    try:
        raiz = ET.parse(SALIDA).getroot()
        canal = raiz.find("channel")

        if canal is None:
            return noticias

        for item in canal.findall("item"):
            clave = identificador(item)

            if clave:
                noticias[clave] = copy.deepcopy(item)

    except ET.ParseError:
        print("El rss.xml anterior no era válido. Se reconstruirá.")

    return noticias


def crear_rss(items: list[ET.Element]) -> ET.ElementTree:
    rss = ET.Element("rss", {"version": "2.0"})
    canal = ET.SubElement(rss, "channel")

    ET.SubElement(canal, "title").text = "Bolsamanía — Todas las noticias"
    ET.SubElement(canal, "link").text = "https://www.bolsamania.com/"
    ET.SubElement(canal, "description").text = (
        "Noticias, mercados, empresas, economía, análisis técnico, "
        "análisis fundamental y criptomonedas publicadas por Bolsamanía."
    )
    ET.SubElement(canal, "language").text = "es-ES"
    ET.SubElement(canal, "lastBuildDate").text = email.utils.format_datetime(
        datetime.now(timezone.utc)
    )
    ET.SubElement(canal, "generator").text = "GitHub Actions"

    for item in items:
        canal.append(copy.deepcopy(item))

    return ET.ElementTree(rss)


def guardar_atomico(arbol: ET.ElementTree) -> None:
    ET.indent(arbol, space="  ")

    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=".",
        prefix="rss_",
        suffix=".xml",
    ) as temporal:
        ruta_temporal = Path(temporal.name)
        arbol.write(
            temporal,
            encoding="utf-8",
            xml_declaration=True,
        )

    os.replace(ruta_temporal, SALIDA)


def main() -> None:
    contenido = descargar_rss()
    raiz_nueva = ET.fromstring(contenido)
    canal_nuevo = raiz_nueva.find("channel")

    if canal_nuevo is None:
        raise RuntimeError("No se encontró el canal RSS de Bolsamanía")

    noticias = cargar_historico()

    for item in canal_nuevo.findall("item"):
        clave = identificador(item)

        if clave:
            noticias[clave] = copy.deepcopy(item)

    ordenadas = sorted(
        noticias.values(),
        key=fecha_item,
        reverse=True,
    )[:MAXIMO_NOTICIAS]

    guardar_atomico(crear_rss(ordenadas))
    print(f"RSS actualizado correctamente: {len(ordenadas)} noticias")


if __name__ == "__main__":
    main()
