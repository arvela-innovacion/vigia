#!/usr/bin/env python3

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from reglas_demo import evaluar

DB = (
    Path.home()
    / "vigilancia/prototipo/datos/demo.db"
)


def ahora():
    return datetime.now().astimezone().isoformat(
        timespec="seconds"
    )


def conectar():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=20000")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def preparar():
    with conectar() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS revisiones_ocr_v6 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consenso_id INTEGER NOT NULL UNIQUE,
            decision TEXT NOT NULL,
            texto_confirmado TEXT,
            observaciones TEXT,
            fecha TEXT NOT NULL,
            FOREIGN KEY(consenso_id)
                REFERENCES consensos_ocr(id)
        );

        CREATE TABLE IF NOT EXISTS evaluaciones_ocr_v6 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT NOT NULL,
            identificador TEXT NOT NULL,
            consenso_id INTEGER NOT NULL,
            resultado_json TEXT NOT NULL,
            fecha TEXT NOT NULL,
            UNIQUE(sesion, identificador),
            FOREIGN KEY(consenso_id)
                REFERENCES consensos_ocr(id)
        );
        """)


def obtener_consenso(db, consenso_id):
    return db.execute("""
        SELECT
            c.id,
            c.texto_candidato,
            c.estado,
            c.fotogramas_distintos,
            c.confianza_media,
            t.track_id,
            t.sesion
        FROM consensos_ocr c
        JOIN tracks_ocr t
            ON t.id = c.track_db_id
        WHERE c.id = ?
    """, (consenso_id,)).fetchone()


def pendientes():
    with conectar() as db:
        filas = db.execute("""
            SELECT
                c.id,
                t.sesion,
                t.track_id,
                c.texto_candidato,
                c.fotogramas_distintos,
                ROUND(c.confianza_media, 3)
                    AS confianza,
                c.estado
            FROM consensos_ocr c
            JOIN tracks_ocr t
                ON t.id = c.track_db_id
            ORDER BY t.sesion, t.track_id
        """).fetchall()

    print("\n=== CONSENSOS OCR ===")

    for f in filas:
        print(
            f"ID={f['id']} "
            f"sesion={f['sesion']} "
            f"track={f['track_id']} "
            f"texto={f['texto_candidato']} "
            f"frames={f['fotogramas_distintos']} "
            f"conf={f['confianza']} "
            f"estado={f['estado']}"
        )

    if not filas:
        print("No hay consensos. Ejecuta primero consolidar_ocr_db.py")


def rechazar(consenso_id, motivo):
    with conectar() as db:
        fila = obtener_consenso(db, consenso_id)

        if fila is None:
            raise ValueError("No existe ese consenso")

        if fila["estado"] != "pendiente_revision":
            raise ValueError(
                "Este consenso ya fue procesado: "
                + fila["estado"]
            )

        db.execute("""
            INSERT INTO revisiones_ocr_v6
            (consenso_id, decision, observaciones, fecha)
            VALUES (?, 'rechazado', ?, ?)
        """, (consenso_id, motivo, ahora()))

        db.execute("""
            UPDATE consensos_ocr
            SET estado = 'rechazado'
            WHERE id = ?
        """, (consenso_id,))

    print("Lectura rechazada. No se generó alerta.")


def verificar(consenso_id, texto_confirmado):
    texto_confirmado = texto_confirmado.strip().upper()

    if not texto_confirmado.isalnum():
        raise ValueError(
            "El identificador debe ser alfanumérico"
        )

    if len(texto_confirmado) > 16:
        raise ValueError("Identificador demasiado largo")

    with conectar() as db:
        fila = obtener_consenso(db, consenso_id)

        if fila is None:
            raise ValueError("No existe ese consenso")

        if fila["estado"] != "pendiente_revision":
            raise ValueError(
                "Este consenso ya fue procesado: "
                + fila["estado"]
            )

        db.execute("""
            INSERT INTO revisiones_ocr_v6
            (consenso_id, decision, texto_confirmado,
             observaciones, fecha)
            VALUES (?, 'verificado', ?, ?, ?)
        """, (
            consenso_id,
            texto_confirmado,
            "Confirmación manual declarada por operador",
            ahora()
        ))

        db.execute("""
            UPDATE consensos_ocr
            SET estado = 'verificado_manual'
            WHERE id = ?
        """, (consenso_id,))

    print("Verificación manual registrada.")
    print("Identificador:", texto_confirmado)
    print("No se ha ejecutado ninguna evaluación todavía.")


def evaluar_verificados():
    with conectar() as db:
        filas = db.execute("""
            SELECT
                r.consenso_id,
                r.texto_confirmado,
                t.sesion,
                t.track_id
            FROM revisiones_ocr_v6 r
            JOIN consensos_ocr c
                ON c.id = r.consenso_id
            JOIN tracks_ocr t
                ON t.id = c.track_db_id
            WHERE r.decision = 'verificado'
            ORDER BY r.id
        """).fetchall()

    print("\n=== EVALUACIÓN DE LECTURAS VERIFICADAS ===")

    for fila in filas:
        sesion = fila["sesion"]
        texto = fila["texto_confirmado"]

        with conectar() as db:
            existe = db.execute("""
                SELECT id
                FROM evaluaciones_ocr_v6
                WHERE sesion = ?
                  AND identificador = ?
            """, (sesion, texto)).fetchone()

        if existe:
            print(
                f"OMITIDO: {texto} ya evaluado "
                f"en sesión {sesion}"
            )
            continue

        # Esta función pertenece al módulo de reglas
        # de DEMOSTRACIÓN. Puede registrar una alerta
        # SIMULADA si coincide con su lista negra.
        resultado = evaluar(
            tipo="matricula",
            identificador=texto,
            confianza=1.0,
            verificado=True,
            origen="manual_demo"
        )

        with conectar() as db:
            db.execute("""
                INSERT INTO evaluaciones_ocr_v6
                (sesion, identificador, consenso_id,
                 resultado_json, fecha)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sesion,
                texto,
                fila["consenso_id"],
                json.dumps(
                    resultado,
                    ensure_ascii=False,
                    default=str
                ),
                ahora()
            ))

        print(
            f"EVALUADO: {texto} "
            f"track={fila['track_id']} "
            f"resultado={resultado}"
        )

    print("\nEvaluación terminada.")


def informe():
    with conectar() as db:
        consultas = {
            "consensos": """
                SELECT COUNT(*) FROM consensos_ocr
            """,
            "pendientes": """
                SELECT COUNT(*) FROM consensos_ocr
                WHERE estado = 'pendiente_revision'
            """,
            "verificados_manualmente": """
                SELECT COUNT(*) FROM consensos_ocr
                WHERE estado = 'verificado_manual'
            """,
            "rechazados": """
                SELECT COUNT(*) FROM consensos_ocr
                WHERE estado = 'rechazado'
            """,
            "evaluaciones": """
                SELECT COUNT(*) FROM evaluaciones_ocr_v6
            """
        }

        print("\n=== INFORME OCR V6 ===")

        for nombre, consulta in consultas.items():
            cantidad = db.execute(consulta).fetchone()[0]
            print(f"{nombre}: {cantidad}")

        print("\n=== EVALUACIONES REGISTRADAS ===")

        filas = db.execute("""
            SELECT
                sesion,
                identificador,
                resultado_json
            FROM evaluaciones_ocr_v6
            ORDER BY id DESC
            LIMIT 20
        """).fetchall()

        for fila in filas:
            print(
                fila["sesion"],
                fila["identificador"],
                fila["resultado_json"]
            )


def main():
    parser = argparse.ArgumentParser()

    grupo = parser.add_mutually_exclusive_group(
        required=True
    )

    grupo.add_argument(
        "--pendientes",
        action="store_true"
    )

    grupo.add_argument(
        "--verificar",
        type=int,
        metavar="CONSENSO_ID"
    )

    grupo.add_argument(
        "--rechazar",
        type=int,
        metavar="CONSENSO_ID"
    )

    grupo.add_argument(
        "--evaluar",
        action="store_true"
    )

    grupo.add_argument(
        "--informe",
        action="store_true"
    )

    parser.add_argument("--texto")
    parser.add_argument("--motivo", default="Lectura incorrecta")

    args = parser.parse_args()

    preparar()

    if args.pendientes:
        pendientes()

    elif args.verificar is not None:
        if not args.texto:
            parser.error(
                "--verificar requiere --texto"
            )
        verificar(args.verificar, args.texto)

    elif args.rechazar is not None:
        rechazar(args.rechazar, args.motivo)

    elif args.evaluar:
        evaluar_verificados()

    elif args.informe:
        informe()


if __name__ == "__main__":
    main()
