#!/usr/bin/env python3

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE = Path.home() / "vigilancia"
PROTO = BASE / "prototipo"
PYTHON = BASE / ".venv/bin/python"
DB = PROTO / "datos/demo.db"


def sesiones():
    with sqlite3.connect(DB) as db:
        return {
            str(fila[0])
            for fila in db.execute(
                "SELECT id FROM sesiones_ocr"
            )
        }


def ejecutar(nombre, *argumentos):
    archivo = PROTO / nombre

    if not archivo.is_file():
        raise FileNotFoundError(
            f"No existe el archivo: {archivo}"
        )

    comando = [
        str(PYTHON),
        str(archivo),
        *map(str, argumentos),
    ]

    print(
        "\n>>> EJECUTANDO:",
        " ".join(comando),
        flush=True,
    )

    subprocess.run(comando, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--fps", type=float, default=3)
    parser.add_argument("--mejores", type=int, default=3)
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()

    if not video.is_file():
        raise SystemExit(f"Vídeo no encontrado: {video}")

    anteriores = sesiones()

    ejecutar(
        "motor_ocr_v5.py",
        "--video", video,
        "--fps", args.fps,
        "--mejores", args.mejores,
    )

    nuevas = sesiones() - anteriores

    if not nuevas:
        raise RuntimeError(
            "El motor no ha registrado una sesión nueva. "
            "Se detiene la consolidación para evitar "
            "trabajar con una sesión anterior."
        )

    print("\nSESIONES NUEVAS:", ", ".join(sorted(nuevas)))

    if len(nuevas) != 1:
        raise RuntimeError(
            "Se han encontrado varias sesiones nuevas. "
            "Se requiere comprobar cuál consolidar."
        )

    ejecutar("consolidar_ocr_db.py")

    print("\nPROCESAMIENTO OCR FINALIZADO")
    print("Sesión nueva:", next(iter(nuevas)))
    print("Comprueba los consensos antes de revisarlos.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(
            f"\nERROR: el proceso terminó con código "
            f"{e.returncode}",
            file=sys.stderr,
        )
        sys.exit(e.returncode)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
