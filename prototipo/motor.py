import argparse
import json
import re
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

BASE = Path.home() / "vigilancia"
PROYECTO = BASE / "prototipo"
DATOS = PROYECTO / "datos"
EVIDENCIAS = DATOS / "evidencias"
DB = DATOS / "demo.db"
MODELO = BASE / "modelos" / "yolo26n_ncnn_model"
PYTHON_OCR = BASE / ".venv-ocr" / "bin" / "python"

EVIDENCIAS.mkdir(parents=True, exist_ok=True)


def conectar():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id TEXT PRIMARY KEY,
            fuente TEXT NOT NULL,
            inicio TEXT NOT NULL,
            fin TEXT,
            fotogramas INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS objetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT NOT NULL,
            track_id INTEGER,
            tipo TEXT NOT NULL,
            primera_vez REAL NOT NULL,
            ultima_vez REAL NOT NULL,
            detecciones INTEGER NOT NULL DEFAULT 1,
            confianza REAL NOT NULL,
            evidencia TEXT,
            UNIQUE(sesion, track_id)
        );

        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objeto_id INTEGER NOT NULL,
            texto TEXT NOT NULL,
            normalizado TEXT NOT NULL,
            confianza REAL NOT NULL,
            estado TEXT NOT NULL,
            FOREIGN KEY(objeto_id) REFERENCES objetos(id)
        );

        CREATE TABLE IF NOT EXISTS listas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            identificador TEXT NOT NULL,
            lista TEXT NOT NULL,
            descripcion TEXT,
            UNIQUE(tipo, identificador)
        );

        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objeto_id INTEGER,
            motivo TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            creada TEXT NOT NULL,
            simulada INTEGER NOT NULL DEFAULT 1
        );
    """)
    db.commit()
    return db


def fecha():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalizar(texto):
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def crear_datos_demo(db):
    ejemplos = [
        ("matricula", "1234BCF", "negra", "Matrícula ficticia de prueba"),
        ("matricula", "5678DEF", "blanca", "Vehículo autorizado ficticio"),
        ("objeto", "perro", "blanca", "Clase permitida en esta demostración")
    ]
    db.executemany(
        """INSERT OR IGNORE INTO listas
           (tipo, identificador, lista, descripcion)
           VALUES (?, ?, ?, ?)""",
        ejemplos
    )
    db.commit()


def ejecutar_ocr(proceso, imagen):
    if proceso is None:
        return []

    try:
        peticion = json.dumps({"imagen": str(imagen)})
        proceso.stdin.write(peticion + "\n")
        proceso.stdin.flush()

        respuesta = proceso.stdout.readline()
        if not respuesta:
            return []

        datos = json.loads(respuesta)
        if "error" in datos:
            print("Aviso OCR:", datos["error"])
        return datos.get("lecturas", [])

    except Exception as exc:
        print("Aviso OCR:", exc)
        return []


def procesar(fuente, muestreo, usar_ocr):
    db = conectar()
    crear_datos_demo(db)

    sesion = uuid.uuid4().hex[:12]
    db.execute(
        "INSERT INTO sesiones (id, fuente, inicio) VALUES (?, ?, ?)",
        (sesion, fuente, fecha())
    )
    db.commit()

    cap = cv2.VideoCapture(
        int(fuente) if fuente.isdigit() else fuente
    )
    if not cap.isOpened():
        db.close()
        raise RuntimeError("No se puede abrir la fuente: " + fuente)

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0

    paso = max(1, round(fps / muestreo))
    modelo = YOLO(str(MODELO))

    proceso_ocr = None
    if usar_ocr:
        try:
            proceso_ocr = subprocess.Popen(
                [str(PYTHON_OCR), "-u",
                 str(PROYECTO / "ocr_worker.py")],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )
        except Exception as exc:
            print("OCR no disponible:", exc)

    # Una lectura inicial por objeto seguido.
    # No se considera identificación de matrícula confirmada.
    ocr_realizado = set()
    objetos = {}
    analizados = 0
    indice = 0
    inicio = time.monotonic()

    vehiculos = {"car", "truck", "bus", "motorcycle"}

    try:
        while True:
            correcto, imagen = cap.read()
            if not correcto:
                break

            if indice % paso:
                indice += 1
                continue

            segundo = indice / fps
            indice += 1
            analizados += 1

            resultado = modelo.track(
                source=imagen,
                persist=True,
                tracker="bytetrack.yaml",
                imgsz=640,
                device="cpu",
                verbose=False
            )[0]

            if resultado.boxes is None or not len(resultado.boxes):
                continue

            anotada = resultado.plot()
            nombre_archivo = f"{sesion}_{analizados:05d}.jpg"
            evidencia = EVIDENCIAS / nombre_archivo
            cv2.imwrite(str(evidencia), anotada)

            for posicion, caja in enumerate(resultado.boxes):
                clase = resultado.names[int(caja.cls[0])]
                confianza = float(caja.conf[0])

                if caja.id is not None:
                    track_id = int(caja.id[0])
                else:
                    # Sin seguimiento estable: identificador único negativo.
                    track_id = -(analizados * 1000 + posicion + 1)

                clave = (sesion, track_id)

                if clave not in objetos:
                    cursor = db.execute(
                        """INSERT INTO objetos
                        (sesion, track_id, tipo, primera_vez,
                         ultima_vez, confianza, evidencia)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (sesion, track_id, clase, segundo,
                         segundo, confianza, nombre_archivo)
                    )
                    objetos[clave] = cursor.lastrowid
                else:
                    db.execute(
                        """UPDATE objetos
                           SET ultima_vez=?,
                               detecciones=detecciones+1,
                               confianza=MAX(confianza, ?)
                           WHERE id=?""",
                        (segundo, confianza, objetos[clave])
                    )

                objeto_id = objetos[clave]

                if (
                    usar_ocr
                    and proceso_ocr is not None
                    and clase in vehiculos
                    and clave not in ocr_realizado
                    and confianza >= 0.55
                ):
                    ocr_realizado.add(clave)

                    x1, y1, x2, y2 = [
                        int(v) for v in caja.xyxy[0].tolist()
                    ]
                    alto, ancho = imagen.shape[:2]
                    x1, x2 = max(0, x1), min(ancho, x2)
                    y1, y2 = max(0, y1), min(alto, y2)

                    if x2 - x1 >= 80 and y2 - y1 >= 40:
                        recorte = imagen[y1:y2, x1:x2]
                        ruta_recorte = (
                            EVIDENCIAS /
                            f"{sesion}_objeto_{objeto_id}.jpg"
                        )
                        cv2.imwrite(str(ruta_recorte), recorte)

                        for lectura in ejecutar_ocr(
                            proceso_ocr, ruta_recorte
                        ):
                            texto = lectura["texto"]
                            limpio = normalizar(texto)
                            certeza = lectura["confianza"]

                            # OCR sobre vehículo completo:
                            # candidato no verificado, no matrícula confirmada.
                            estado = "pendiente_revision"

                            db.execute(
                                """INSERT INTO lecturas
                                (objeto_id, texto, normalizado,
                                 confianza, estado)
                                VALUES (?, ?, ?, ?, ?)""",
                                (objeto_id, texto, limpio,
                                 certeza, estado)
                            )

                print(
                    f"{segundo:5.1f}s | ID {track_id:3d} | "
                    f"{clase:14s} | {confianza:.0%}"
                )

            db.commit()

    finally:
        cap.release()

        if proceso_ocr is not None:
            try:
                proceso_ocr.stdin.close()
                proceso_ocr.terminate()
                proceso_ocr.wait(timeout=3)
            except Exception:
                proceso_ocr.kill()

        db.execute(
            """UPDATE sesiones
               SET fin=?, fotogramas=?
               WHERE id=?""",
            (fecha(), analizados, sesion)
        )
        db.commit()

        total = db.execute(
            "SELECT COUNT(*) FROM objetos WHERE sesion=?",
            (sesion,)
        ).fetchone()[0]

        lecturas = db.execute(
            """SELECT COUNT(*) FROM lecturas
               JOIN objetos ON objetos.id=lecturas.objeto_id
               WHERE objetos.sesion=?""",
            (sesion,)
        ).fetchone()[0]

        db.close()

        print("\n--- RESUMEN ---")
        print("Sesión:", sesion)
        print("Fotogramas analizados:", analizados)
        print("Objetos seguidos:", total)
        print("Textos OCR candidatos:", lecturas)
        print("Tiempo real de ejecución:",
              round(time.monotonic() - inicio, 2), "segundos")
        print("Base de datos:", DB)


def simular_alerta():
    db = conectar()
    crear_datos_demo(db)

    db.execute(
        """INSERT INTO alertas
           (objeto_id, motivo, estado, creada, simulada)
           VALUES (NULL, ?, 'pendiente', ?, 1)""",
        (
            "SIMULACIÓN: coincidencia con matrícula ficticia "
            "1234BCF de la lista negra. Requiere revisión humana.",
            fecha()
        )
    )
    db.commit()
    db.close()
    print("Alerta de demostración creada.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fuente",
        default=str(BASE / "videos" / "trafico_prueba.mp4")
    )
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--simular-alerta", action="store_true")
    args = parser.parse_args()

    if args.simular_alerta:
        simular_alerta()
    else:
        procesar(args.fuente, args.fps, args.ocr)
