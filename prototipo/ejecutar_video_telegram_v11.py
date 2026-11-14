#!/usr/bin/env python3

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path.home() / "vigilancia"
PROTO = BASE / "prototipo"
PYTHON = BASE / ".venv/bin/python"
DB = PROTO / "datos/demo.db"


def conectar():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def obtener_sesiones():
    with conectar() as db:
        return {
            fila["id"]
            for fila in db.execute(
                "SELECT id FROM sesiones_ocr"
            )
        }


def enviar_telegram(mensaje):
    token = os.environ.get(
        "VIG_TELEGRAM_TOKEN", ""
    ).strip()

    chat_id = os.environ.get(
        "VIG_TELEGRAM_CHAT_ID", ""
    ).strip()

    if not token or not chat_id:
        print(
            "Telegram no configurado en esta terminal."
        )
        return False

    url = (
        "https://api.telegram.org/bot"
        + token
        + "/sendMessage"
    )

    datos = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": mensaje,
    }).encode()

    peticion = urllib.request.Request(
        url,
        data=datos,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            peticion, timeout=20
        ) as respuesta:
            resultado = json.load(respuesta)

        return resultado.get("ok") is True

    except Exception:
        # No mostrar excepciones que puedan
        # incluir el token en la URL.
        print("No se pudo enviar el mensaje.")
        return False


def ejecutar_video(video, fps, mejores):
    comando = [
        str(PYTHON),
        str(PROTO / "ejecutar_ocr_v7.py"),
        "--video", str(video),
        "--fps", str(fps),
        "--mejores", str(mejores),
    ]

    subprocess.run(comando, check=True)


def obtener_resumen(sesion):
    with conectar() as db:
        datos = db.execute("""
            SELECT
                s.id,
                s.fotogramas,
                s.intentos,
                s.errores
            FROM sesiones_ocr s
            WHERE s.id = ?
        """, (sesion,)).fetchone()

        consensos = db.execute("""
            SELECT
                c.id,
                c.texto_candidato,
                c.confianza_media,
                c.fotogramas_distintos,
                c.estado
            FROM consensos_ocr c
            JOIN tracks_ocr t
              ON t.id = c.track_db_id
            WHERE t.sesion = ?
            ORDER BY c.id
        """, (sesion,)).fetchall()

    return datos, consensos


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--video", required=True
    )
    parser.add_argument(
        "--fps", type=float, default=3
    )
    parser.add_argument(
        "--mejores", type=int, default=3
    )

    args = parser.parse_args()

    video = Path(args.video).expanduser()

    if not video.is_file():
        raise SystemExit("Vídeo no encontrado.")

    anteriores = obtener_sesiones()

    print("\n=== PROCESANDO VIDEO ===")

    ejecutar_video(
        video,
        args.fps,
        args.mejores,
    )

    nuevas = obtener_sesiones() - anteriores

    if len(nuevas) != 1:
        raise SystemExit(
            "No se pudo identificar una única "
            "sesión nueva. No se enviará resumen."
        )

    sesion = next(iter(nuevas))

    datos, consensos = obtener_resumen(sesion)

    lineas = [
        "📹 VIGILANCIA PI - VIDEO PROCESADO",
        "",
        f"Sesión: {sesion}",
        f"Fotogramas: {datos['fotogramas']}",
        f"Intentos OCR: {datos['intentos']}",
        f"Errores OCR: {datos['errores']}",
        f"Consensos: {len(consensos)}",
        "",
        "LECTURAS CANDIDATAS:",
    ]

    if not consensos:
        lineas.append("Ninguna.")

    for consenso in consensos:
        lineas.append(
            f"ID {consenso['id']}: "
            f"{consenso['texto_candidato']} "
            f"(conf. {consenso['confianza_media']:.2f}) "
            f"[{consenso['estado']}]"
        )

    lineas.extend([
        "",
        "Estas lecturas no están verificadas.",
        "No se generan alertas críticas "
        "por OCR sin confirmar.",
        "",
        "FIN DEL PROCESAMIENTO.",
    ])

    mensaje = "\n".join(lineas)

    print("\n" + mensaje)

    if enviar_telegram(mensaje):
        print("\nRESUMEN ENVIADO A TELEGRAM")
    else:
        print("\nRESUMEN NO ENVIADO")
        sys.exit(1)


if __name__ == "__main__":
    main()
