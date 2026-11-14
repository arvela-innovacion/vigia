#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse
import csv
import re
import sqlite3
import uuid

BASE = Path.home() / "vigilancia"
DB = BASE / "prototipo" / "datos" / "demo.db"
CSV_ANTERIOR = (
    BASE / "prototipo" / "datos" / "banco_ocr_v4"
    / "matriculas_prueba" / "resultados.csv"
)


def fecha():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalizar(texto):
    return re.sub(r"[^A-Z0-9]", "", str(texto).upper())


def conectar():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def preparar():
    with conectar() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sesiones_ocr (
            id TEXT PRIMARY KEY,
            fuente TEXT NOT NULL,
            inicio TEXT NOT NULL,
            fin TEXT,
            fotogramas INTEGER DEFAULT 0,
            intentos INTEGER DEFAULT 0,
            errores INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tracks_ocr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT NOT NULL,
            track_id INTEGER NOT NULL,
            clase TEXT,
            UNIQUE(sesion, track_id),
            FOREIGN KEY(sesion) REFERENCES sesiones_ocr(id)
        );

        CREATE TABLE IF NOT EXISTS lecturas_ocr_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_db_id INTEGER NOT NULL,
            fotograma INTEGER NOT NULL,
            region TEXT NOT NULL,
            texto TEXT NOT NULL,
            normalizado TEXT NOT NULL,
            confianza REAL NOT NULL,
            evidencia TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente_revision',
            FOREIGN KEY(track_db_id) REFERENCES tracks_ocr(id)
        );

        CREATE INDEX IF NOT EXISTS idx_ocr_v2_track
            ON lecturas_ocr_v2(track_db_id);

        CREATE INDEX IF NOT EXISTS idx_ocr_v2_texto
            ON lecturas_ocr_v2(normalizado);
        """)


def crear_sesion(fuente, identificador=None):
    sid = identificador or ("ocr_" + uuid.uuid4().hex[:12])
    with conectar() as db:
        db.execute(
            """INSERT INTO sesiones_ocr(id, fuente, inicio)
               VALUES (?, ?, ?)""",
            (sid, str(fuente), fecha())
        )
    return sid


def guardar_lectura(sesion, track_id, clase, fotograma,
                    region, texto, confianza, evidencia=None):
    texto = str(texto).strip()
    limpio = normalizar(texto)

    if not limpio:
        return False

    with conectar() as db:
        db.execute(
            """INSERT OR IGNORE INTO tracks_ocr
               (sesion, track_id, clase)
               VALUES (?, ?, ?)""",
            (sesion, int(track_id), clase)
        )

        track = db.execute(
            """SELECT id FROM tracks_ocr
               WHERE sesion=? AND track_id=?""",
            (sesion, int(track_id))
        ).fetchone()["id"]

        db.execute(
            """INSERT INTO lecturas_ocr_v2
               (track_db_id, fotograma, region, texto,
                normalizado, confianza, evidencia)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                track, int(fotograma), region, texto,
                limpio, float(confianza),
                str(evidencia) if evidencia else None
            )
        )

    return True


def cerrar_sesion(sesion, fotogramas=0, intentos=0, errores=0):
    with conectar() as db:
        db.execute(
            """UPDATE sesiones_ocr
               SET fin=?, fotogramas=?, intentos=?, errores=?
               WHERE id=?""",
            (fecha(), fotogramas, intentos, errores, sesion)
        )


def importar_csv():
    if not CSV_ANTERIOR.is_file():
        raise FileNotFoundError(CSV_ANTERIOR)

    # Identificador fijo para impedir importaciones duplicadas.
    sid = "importacion_matriculas_v4"

    with conectar() as db:
        existe = db.execute(
            "SELECT 1 FROM sesiones_ocr WHERE id=?", (sid,)
        ).fetchone()

    if existe:
        print("La importación V4 ya existe. No se duplica.")
        return sid

    sid = crear_sesion(CSV_ANTERIOR, sid)
    cantidad = 0

    with CSV_ANTERIOR.open(
        encoding="utf-8", newline=""
    ) as archivo:
        for fila in csv.DictReader(archivo):
            evidencia = CSV_ANTERIOR.parent / fila["archivo"]

            if guardar_lectura(
                sid,
                fila["track_id"],
                fila["clase"],
                fila["fotograma"],
                fila["region"],
                fila["texto"],
                fila["confianza"],
                evidencia
            ):
                cantidad += 1

    cerrar_sesion(sid, intentos=24)
    print("Lecturas importadas:", cantidad)
    return sid


def consenso(sesion):
    with conectar() as db:
        filas = db.execute(
            """SELECT t.track_id, t.clase,
                      l.fotograma, l.normalizado, l.confianza
               FROM lecturas_ocr_v2 l
               JOIN tracks_ocr t ON t.id=l.track_db_id
               WHERE t.sesion=?
               ORDER BY t.track_id, l.fotograma""",
            (sesion,)
        ).fetchall()

    grupos = defaultdict(list)

    for fila in filas:
        grupos[fila["track_id"]].append(fila)

    resultados = []

    for track_id, lecturas in sorted(grupos.items()):
        textos = defaultdict(lambda: {
            "fotogramas": set(),
            "confianzas": []
        })

        for lectura in lecturas:
            item = textos[lectura["normalizado"]]
            item["fotogramas"].add(lectura["fotograma"])
            item["confianzas"].append(lectura["confianza"])

        ordenados = sorted(
            textos.items(),
            key=lambda x: (
                len(x[1]["fotogramas"]),
                sum(x[1]["confianzas"]) /
                len(x[1]["confianzas"])
            ),
            reverse=True
        )

        principal, datos = ordenados[0]

        resultados.append({
            "track_id": track_id,
            "clase": lecturas[0]["clase"],
            "texto_candidato": principal,
            "fotogramas_distintos": len(datos["fotogramas"]),
            "confianza_media": round(
                sum(datos["confianzas"]) /
                len(datos["confianzas"]), 3
            ),
            "alternativas": [
                texto for texto, _ in ordenados[1:]
            ],
            "estado": "PENDIENTE_REVISION",
            "verificado": False
        })

    return resultados


def mostrar(sesion):
    with conectar() as db:
        resumen = db.execute(
            """SELECT COUNT(*) AS lecturas,
                      COUNT(DISTINCT t.track_id) AS tracks
               FROM lecturas_ocr_v2 l
               JOIN tracks_ocr t ON t.id=l.track_db_id
               WHERE t.sesion=?""",
            (sesion,)
        ).fetchone()

    print("\n=== OCR GUARDADO EN SQLITE ===")
    print("Sesión:", sesion)
    print("Lecturas:", resumen["lecturas"])
    print("Tracks con texto:", resumen["tracks"])

    for item in consenso(sesion):
        print(
            f"Track {item['track_id']} | "
            f"{item['texto_candidato']} | "
            f"fotogramas={item['fotogramas_distintos']} | "
            f"conf={item['confianza_media']:.2f} | "
            f"alternativas={item['alternativas']}"
        )

    print("\nTodas las lecturas pendientes de revisión.")
    print("Alertas creadas por OCR: 0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--importar", action="store_true")
    parser.add_argument("--sesion")
    args = parser.parse_args()

    preparar()

    if args.importar:
        mostrar(importar_csv())
    elif args.sesion:
        mostrar(args.sesion)
    else:
        print("Base de datos OCR preparada:", DB)
