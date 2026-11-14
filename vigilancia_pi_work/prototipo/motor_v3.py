#!/usr/bin/env python3
"""
Vigilancia Pi V3
Detección real + seguimiento + reglas de demostración.

IMPORTANTE:
- Las detecciones de objetos proceden del vídeo.
- Los identificadores de matrícula/persona son FICTICIOS.
- No se atribuye ninguna identidad real a los objetos detectados.
- Las alertas son exclusivamente simuladas.
"""

from pathlib import Path
from datetime import datetime
from collections import Counter
import argparse
import json
import sqlite3
import time
import uuid

import cv2
from ultralytics import YOLO

from reglas_demo import preparar, evaluar, conectar

BASE = Path.home() / "vigilancia"
VIDEO = BASE / "videos" / "trafico_prueba.mp4"
MODELO = BASE / "modelos" / "yolo26n_ncnn_model"
DATOS = BASE / "prototipo" / "datos"
EVIDENCIAS = DATOS / "evidencias_v3"

VEHICULOS = {"car", "truck", "bus", "motorcycle"}

# Escenarios ficticios. Ninguna matrícula se ha leído del vídeo.
ESCENARIOS = [
    ("matricula", "1234BCF", 0.99, True),
    ("matricula", "5678DEF", 0.99, True),
    ("matricula", "TEST999", 0.98, True),
    ("matricula", "9999ZZZ", 0.99, True),
    ("matricula", "1234BCF", 0.61, False),
]

ESCENARIOS_PERSONAS = [
    ("persona_demo", "DEMO-P001", 1.0, True),
    ("persona_demo", "DEMO-P002", 1.0, True),
]


def fecha():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def preparar_v3():
    preparar()
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)

    with conectar() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sesiones_v3 (
            id TEXT PRIMARY KEY,
            fuente TEXT NOT NULL,
            inicio TEXT NOT NULL,
            fin TEXT,
            fotogramas INTEGER DEFAULT 0,
            detecciones INTEGER DEFAULT 0,
            simulacion INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS detecciones_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT NOT NULL,
            fotograma INTEGER NOT NULL,
            segundo REAL NOT NULL,
            track_id INTEGER,
            clase TEXT NOT NULL,
            confianza REAL NOT NULL,
            x1 INTEGER NOT NULL,
            y1 INTEGER NOT NULL,
            x2 INTEGER NOT NULL,
            y2 INTEGER NOT NULL,
            evidencia TEXT,
            FOREIGN KEY(sesion) REFERENCES sesiones_v3(id)
        );

        CREATE TABLE IF NOT EXISTS enlaces_demo_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT NOT NULL,
            deteccion_id INTEGER NOT NULL,
            evaluacion_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            identificador_ficticio TEXT NOT NULL,
            resultado TEXT NOT NULL,
            alerta_id INTEGER,
            nota TEXT NOT NULL,
            FOREIGN KEY(deteccion_id) REFERENCES detecciones_v3(id),
            FOREIGN KEY(evaluacion_id) REFERENCES evaluaciones_demo(id)
        );
        """)


def ejecutar(ruta_video, fps_objetivo=5, max_fotogramas=0):
    preparar_v3()

    if not ruta_video.is_file():
        raise FileNotFoundError(f"No existe el vídeo: {ruta_video}")

    if not MODELO.is_dir():
        raise FileNotFoundError(f"No existe el modelo: {MODELO}")

    sesion = "v3_" + uuid.uuid4().hex[:12]
    carpeta = EVIDENCIAS / sesion
    carpeta.mkdir(parents=True, exist_ok=True)

    modelo = YOLO(str(MODELO))
    cap = cv2.VideoCapture(str(ruta_video))

    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir el vídeo")

    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30
    paso = max(1, round(fps_video / fps_objetivo))

    total_fotogramas = 0
    analizados = 0
    total_detecciones = 0
    clases = Counter()
    ids_seguidos = set()

    # Una prueba ficticia por escenario y por detección distinta.
    indice_vehiculo = 0
    indice_persona = 0
    usados = set()
    enlaces = []

    inicio = time.monotonic()

    with conectar() as db:
        db.execute(
            """INSERT INTO sesiones_v3 (id, fuente, inicio)
               VALUES (?, ?, ?)""",
            (sesion, str(ruta_video), fecha())
        )

    try:
        while True:
            correcto, imagen = cap.read()
            if not correcto:
                break

            fotograma = total_fotogramas
            total_fotogramas += 1

            if fotograma % paso != 0:
                continue

            if max_fotogramas and analizados >= max_fotogramas:
                break

            analizados += 1
            segundo = fotograma / fps_video

            resultados = modelo.track(
                source=imagen,
                persist=True,
                tracker="bytetrack.yaml",
                imgsz=640,
                device="cpu",
                verbose=False,
                conf=0.25
            )

            if not resultados:
                continue

            resultado = resultados[0]
            if resultado.boxes is None:
                continue

            # Guardamos evidencia únicamente cuando hay detecciones.
            ruta_evidencia = None

            if len(resultado.boxes) > 0:
                ruta_evidencia = carpeta / f"frame_{fotograma:06d}.jpg"
                cv2.imwrite(
                    str(ruta_evidencia),
                    resultado.plot()
                )

            for caja in resultado.boxes:
                clase = resultado.names[int(caja.cls[0])]
                confianza = float(caja.conf[0])

                x1, y1, x2, y2 = [
                    int(v) for v in caja.xyxy[0].tolist()
                ]

                track_id = None

                if caja.id is not None:
                    track_id = int(caja.id[0])
                    ids_seguidos.add((clase, track_id))

                clases[clase] += 1
                total_detecciones += 1

                with conectar() as db:
                    cursor = db.execute(
                        """INSERT INTO detecciones_v3
                           (sesion, fotograma, segundo, track_id,
                            clase, confianza, x1, y1, x2, y2,
                            evidencia)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sesion, fotograma, segundo, track_id,
                            clase, confianza, x1, y1, x2, y2,
                            str(ruta_evidencia) if ruta_evidencia else None
                        )
                    )
                    deteccion_id = cursor.lastrowid

                # Solo usamos detecciones diferentes para los escenarios.
                # No estamos identificando al vehículo ni a la persona.
                clave = (
                    clase,
                    track_id if track_id is not None else
                    f"sin_track_{fotograma}_{deteccion_id}"
                )

                if clave in usados:
                    continue

                escenario = None

                if (
                    clase in VEHICULOS
                    and indice_vehiculo < len(ESCENARIOS)
                ):
                    escenario = ESCENARIOS[indice_vehiculo]
                    indice_vehiculo += 1

                elif (
                    clase == "person"
                    and indice_persona < len(ESCENARIOS_PERSONAS)
                ):
                    escenario = ESCENARIOS_PERSONAS[indice_persona]
                    indice_persona += 1

                if escenario is None:
                    continue

                usados.add(clave)
                tipo, identificador, confianza_demo, verificado = escenario

                evaluacion = evaluar(
                    tipo=tipo,
                    identificador=identificador,
                    confianza=confianza_demo,
                    verificado=verificado,
                    origen="manual_demo"
                )

                nota = (
                    "ESCENARIO SIMULADO: la detección visual es real, "
                    "pero el identificador fue asignado artificialmente "
                    "para probar las reglas. No representa la identidad "
                    "del objeto grabado."
                )

                with conectar() as db:
                    db.execute(
                        """INSERT INTO enlaces_demo_v3
                           (sesion, deteccion_id, evaluacion_id,
                            tipo, identificador_ficticio,
                            resultado, alerta_id, nota)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sesion,
                            deteccion_id,
                            evaluacion["evaluacion_id"],
                            tipo,
                            identificador,
                            evaluacion["resultado"],
                            evaluacion["alerta_id"],
                            nota
                        )
                    )

                enlaces.append({
                    "clase_detectada": clase,
                    "track_id": track_id,
                    "identificador_ficticio": identificador,
                    "resultado": evaluacion["resultado"],
                    "alerta_id": evaluacion["alerta_id"],
                })

    finally:
        cap.release()

        with conectar() as db:
            db.execute(
                """UPDATE sesiones_v3
                   SET fin=?, fotogramas=?, detecciones=?
                   WHERE id=?""",
                (
                    fecha(),
                    analizados,
                    total_detecciones,
                    sesion
                )
            )

    duracion = time.monotonic() - inicio

    informe = {
        "sesion": sesion,
        "fuente": str(ruta_video),
        "modo": "SIMULACION_CON_DETECCIONES_REALES",
        "fotogramas_analizados": analizados,
        "detecciones": total_detecciones,
        "tracks_distintos": len(ids_seguidos),
        "clases": dict(clases),
        "escenarios_ejecutados": len(enlaces),
        "resultados": dict(Counter(
            x["resultado"] for x in enlaces
        )),
        "segundos_procesamiento": round(duracion, 2),
        "escenarios": enlaces
    }

    ruta_informe = carpeta / "informe.json"
    ruta_informe.write_text(
        json.dumps(informe, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print("VIGILANCIA PI V3 - INFORME DE EJECUCIÓN")
    print("=" * 60)
    print("Sesión:", sesion)
    print("Fotogramas analizados:", analizados)
    print("Detecciones reales:", total_detecciones)
    print("Tracks distintos:", len(ids_seguidos))
    print("Clases detectadas:", dict(clases))
    print("Tiempo:", round(duracion, 2), "segundos")

    print("\n=== ESCENARIOS FICTICIOS ===")

    for x in enlaces:
        print(
            f"{x['clase_detectada']:12s} "
            f"track={str(x['track_id']):5s} "
            f"DEMO={x['identificador_ficticio']:12s} "
            f"=> {x['resultado']:16s} "
            f"alerta={x['alerta_id']}"
        )

    print("\n=== RESUMEN DE RESULTADOS ===")
    for resultado, cantidad in informe["resultados"].items():
        print(f"{resultado}: {cantidad}")

    print("\nInforme JSON:", ruta_informe)
    print("Base de datos:", DATOS / "demo.db")
    print("\nAVISO: identificadores y alertas simulados.")

    return informe


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=str(VIDEO))
    parser.add_argument("--fps", type=float, default=5)
    parser.add_argument("--max-fotogramas", type=int, default=0)
    args = parser.parse_args()

    if args.fps <= 0:
        parser.error("--fps debe ser mayor que cero")

    ejecutar(
        Path(args.video),
        args.fps,
        args.max_fotogramas
    )
