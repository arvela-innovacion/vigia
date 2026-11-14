#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path

BASE = Path.home() / "vigilancia"
PROTO = BASE / "prototipo"
PYTHON = BASE / ".venv/bin/python"


def ejecutar(archivo, *argumentos):
    comando = [
        str(PYTHON),
        str(PROTO / archivo),
        *map(str, argumentos)
    ]

    print(
        "\n>>>",
        archivo,
        " ".join(map(str, argumentos)),
        flush=True
    )

    subprocess.run(comando, check=True)


def main():
    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="accion",
        required=True
    )

    p_video = sub.add_parser("procesar")
    p_video.add_argument("--video", required=True)
    p_video.add_argument("--fps", type=float, default=3)
    p_video.add_argument("--mejores", type=int, default=3)

    sub.add_parser("pendientes")
    sub.add_parser("notificar")
    sub.add_parser("estado")

    args = parser.parse_args()

    if args.accion == "procesar":
        ejecutar(
            "ejecutar_ocr_v7.py",
            "--video", args.video,
            "--fps", args.fps,
            "--mejores", args.mejores
        )

        print("\nPROCESAMIENTO FINALIZADO")
        print("Consensos guardados en SQLite.")
        print("Pendientes de revisión humana.")

        ejecutar(
            "revision_ocr_v6.py",
            "--pendientes"
        )

    elif args.accion == "pendientes":
        ejecutar(
            "revision_ocr_v6.py",
            "--pendientes"
        )

    elif args.accion == "notificar":
        # Solo evalúa consensos verificados manualmente.
        ejecutar(
            "revision_ocr_v6.py",
            "--evaluar"
        )

        # Solo notifica resultados CRITICO_ALERTA.
        ejecutar(
            "alertas_telegram_v9.py",
            "--enviar"
        )

        ejecutar(
            "notificador_v8.py",
            "--listar"
        )

    elif args.accion == "estado":
        ejecutar(
            "revision_ocr_v6.py",
            "--informe"
        )

        ejecutar(
            "notificador_v8.py",
            "--listar"
        )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(
            f"\nERROR: proceso terminado con código "
            f"{e.returncode}"
        )
        sys.exit(e.returncode)
