from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sqlite3

DB = (
    Path.home()
    / "vigilancia/prototipo/datos/demo.db"
)


def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def consolidar():
    with conectar() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS consensos_ocr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_db_id INTEGER NOT NULL UNIQUE,
                texto_candidato TEXT NOT NULL,
                fotogramas_distintos INTEGER NOT NULL,
                confianza_media REAL NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente_revision',
                actualizado TEXT NOT NULL,
                FOREIGN KEY(track_db_id) REFERENCES tracks_ocr(id)
            )
        """)

        sesiones = db.execute("""
            SELECT id FROM sesiones_ocr
            WHERE fuente LIKE '%matriculas_prueba.mp4'
            ORDER BY inicio DESC
            LIMIT 1
        """).fetchall()

        if not sesiones:
            print("No hay sesiones OCR de vídeo.")
            return

        sesion = sesiones[0]["id"]

        lecturas = db.execute("""
            SELECT
                t.id AS track_db_id,
                t.track_id,
                l.normalizado,
                l.fotograma,
                l.confianza
            FROM tracks_ocr t
            JOIN lecturas_ocr_v2 l
                ON l.track_db_id = t.id
            WHERE t.sesion = ?
            ORDER BY t.track_id
        """, (sesion,)).fetchall()

        grupos = defaultdict(list)

        for lectura in lecturas:
            grupos[lectura["track_db_id"]].append(lectura)

        print("Sesión:", sesion)
        print("\n=== CONSENSOS GUARDADOS ===")

        for track_db_id, filas in grupos.items():
            textos = defaultdict(lambda: {
                "frames": set(),
                "confianzas": []
            })

            for fila in filas:
                dato = textos[fila["normalizado"]]
                dato["frames"].add(fila["fotograma"])
                dato["confianzas"].append(fila["confianza"])

            ordenados = sorted(
                textos.items(),
                key=lambda x: (
                    len(x[1]["frames"]),
                    sum(x[1]["confianzas"]) /
                    len(x[1]["confianzas"])
                ),
                reverse=True
            )

            texto, datos = ordenados[0]

            cantidad = len(datos["frames"])
            confianza = (
                sum(datos["confianzas"]) /
                len(datos["confianzas"])
            )

            fecha = datetime.now().astimezone().isoformat(
                timespec="seconds"
            )

            db.execute("""
                INSERT INTO consensos_ocr (
                    track_db_id,
                    texto_candidato,
                    fotogramas_distintos,
                    confianza_media,
                    estado,
                    actualizado
                )
                VALUES (?, ?, ?, ?, 'pendiente_revision', ?)
                ON CONFLICT(track_db_id)
                DO UPDATE SET
                    texto_candidato = excluded.texto_candidato,
                    fotogramas_distintos = excluded.fotogramas_distintos,
                    confianza_media = excluded.confianza_media,
                    actualizado = excluded.actualizado
            """, (
                track_db_id,
                texto,
                cantidad,
                confianza,
                fecha
            ))

            print(
                f"Track {filas[0]['track_id']} | "
                f"{texto} | "
                f"{cantidad} fotogramas | "
                f"confianza {confianza:.2f}"
            )

        print("\nConsensos almacenados en SQLite.")


if __name__ == "__main__":
    consolidar()
