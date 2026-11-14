#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path

from notificador_v8 import preparar, encolar, procesar

DB = Path.home() / "vigilancia/prototipo/datos/demo.db"


def conectar():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    return db


def obtener_eventos():
    with conectar() as db:
        return db.execute("""
            SELECT
                e.id AS evaluacion_id,
                e.sesion,
                e.identificador,
                e.consenso_id,
                e.resultado_json,
                c.estado AS estado_consenso,
                r.decision,
                r.texto_confirmado

            FROM evaluaciones_ocr_v6 e

            JOIN consensos_ocr c
              ON c.id = e.consenso_id

            JOIN revisiones_ocr_v6 r
              ON r.id = (
                  SELECT MAX(r2.id)
                  FROM revisiones_ocr_v6 r2
                  WHERE r2.consenso_id = e.consenso_id
              )

            ORDER BY e.id
        """).fetchall()


def preparar_eventos():
    preparar()

    nuevas = 0
    omitidas = 0

    for evento in obtener_eventos():

        try:
            resultado = json.loads(
                evento["resultado_json"]
            )
        except (TypeError, ValueError):
            print(
                "OMITIDO:",
                evento["evaluacion_id"],
                "JSON inválido"
            )
            omitidas += 1
            continue

        valido = (
            isinstance(resultado, dict)
            and resultado.get("resultado") == "CRITICO_ALERTA"
            and resultado.get("simulacion") is True
            and resultado.get("identificador")
                == evento["identificador"]
            and evento["decision"] == "verificado"
            and evento["estado_consenso"]
                == "verificado_manual"
            and evento["texto_confirmado"]
                == evento["identificador"]
        )

        if not valido:
            print(
                "OMITIDO:",
                evento["evaluacion_id"],
                "No cumple las condiciones"
            )
            omitidas += 1
            continue

        clave = (
            f"OCR-DEMO-CRITICO:"
            f"{evento['evaluacion_id']}"
        )

        mensaje = (
            "🚨 ALERTA CRÍTICA - SIMULACIÓN\n\n"
            f"Identificador: {evento['identificador']}\n"
            f"Sesión: {evento['sesion']}\n"
            f"Consenso: {evento['consenso_id']}\n"
            f"Evaluación: {evento['evaluacion_id']}\n"
            f"Alerta interna: {resultado.get('alerta_id')}\n"
            "Resultado: CRITICO_ALERTA\n\n"
            "Coincidencia con lista negra ficticia.\n"
            "Revisión manual registrada.\n\n"
            "DEMOSTRACIÓN: no es una alerta policial real."
        )

        creada = encolar(
            clave=clave,
            canal="telegram",
            mensaje=mensaje,
            nivel="CRITICO"
        )

        if creada:
            nuevas += 1
            print(
                "NUEVA NOTIFICACIÓN:",
                evento["identificador"]
            )
        else:
            print(
                "YA REGISTRADA:",
                evento["identificador"]
            )

    print("\n=== RESUMEN ===")
    print("Nuevas:", nuevas)
    print("Omitidas:", omitidas)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enviar",
        action="store_true"
    )
    args = parser.parse_args()

    preparar_eventos()

    if args.enviar:
        print("\n=== ENVÍO TELEGRAM ===")
        procesar()


if __name__ == "__main__":
    main()
