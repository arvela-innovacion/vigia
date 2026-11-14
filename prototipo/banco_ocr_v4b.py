#!/usr/bin/env python3

from pathlib import Path
from collections import defaultdict, Counter
import argparse
import csv
import json
import subprocess
import cv2

from ultralytics import YOLO

BASE = Path.home() / "vigilancia"
MODELO = BASE / "modelos" / "yolo26n_ncnn_model"
PYTHON_OCR = BASE / ".venv-ocr" / "bin" / "python"
WORKER = BASE / "prototipo" / "ocr_worker.py"
SALIDA = BASE / "prototipo" / "datos" / "banco_ocr_v4"

VEHICULOS = {"car", "truck", "bus", "motorcycle"}


def calidad(imagen):
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    nitidez = cv2.Laplacian(gris, cv2.CV_64F).var()
    alto, ancho = imagen.shape[:2]
    return min(nitidez, 1000) * min(ancho * alto, 300000)


def ejecutar(video, fps_objetivo, mejores):
    if not video.is_file():
        raise FileNotFoundError(video)

    if not WORKER.is_file():
        raise FileNotFoundError(WORKER)

    carpeta = SALIDA / video.stem
    carpeta.mkdir(parents=True, exist_ok=True)

    modelo = YOLO(str(MODELO))
    cap = cv2.VideoCapture(str(video))

    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir el vídeo")

    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30
    paso = max(1, round(fps_video / fps_objetivo))

    muestras = defaultdict(list)
    observaciones = Counter()

    fotograma = 0
    analizados = 0

    print("Vídeo:", video)
    print("FPS originales:", round(fps_video, 2))
    print("Paso entre fotogramas:", paso, flush=True)

    while True:
        correcto, imagen = cap.read()

        if not correcto:
            break

        if fotograma % paso:
            fotograma += 1
            continue

        analizados += 1

        resultado = modelo.track(
            source=imagen,
            persist=True,
            tracker="bytetrack.yaml",
            imgsz=640,
            conf=0.25,
            device="cpu",
            verbose=False
        )[0]

        if resultado.boxes is not None:
            for caja in resultado.boxes:
                clase = resultado.names[int(caja.cls[0])]

                if clase not in VEHICULOS:
                    continue

                observaciones[clase] += 1

                if caja.id is None:
                    continue

                track_id = int(caja.id[0])

                x1, y1, x2, y2 = map(
                    int, caja.xyxy[0].tolist()
                )

                alto, ancho = imagen.shape[:2]

                x1 = max(0, min(ancho, x1))
                x2 = max(0, min(ancho, x2))
                y1 = max(0, min(alto, y1))
                y2 = max(0, min(alto, y2))

                if x2 - x1 < 80 or y2 - y1 < 40:
                    continue

                recorte = imagen[y1:y2, x1:x2].copy()

                # Agrupamos por track_id, aunque YOLO cambie
                # la clase de car a truck en otro fotograma.
                clave = track_id

                muestras[clave].append((
                    calidad(recorte),
                    fotograma,
                    clase,
                    recorte
                ))

                muestras[clave].sort(
                    key=lambda x: x[0],
                    reverse=True
                )

                muestras[clave] = muestras[clave][:mejores]

        fotograma += 1

        if analizados % 100 == 0:
            print(
                "Fotogramas analizados:", analizados,
                "tracks:", len(muestras),
                flush=True
            )

    cap.release()

    print("\n=== DETECCIÓN ===")
    print("Fotogramas analizados:", analizados)
    print("Observaciones:", dict(observaciones))
    print("Tracks con recortes:", len(muestras))

    # OCR independiente: no mezclamos librerías entre entornos.
    proceso = subprocess.Popen(
        [str(PYTHON_OCR), "-u", str(WORKER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

    registros = []
    intentos = 0
    errores = 0

    try:
        for track_id, seleccion in sorted(muestras.items()):
            for posicion, (_, frame, clase, recorte) in enumerate(seleccion):

                alto, ancho = recorte.shape[:2]

                regiones = {
                    "vehiculo": recorte,
                    "mitad_inferior": recorte[alto // 2:, :]
                }

                for region, imagen_region in regiones.items():
                    if imagen_region.size == 0:
                        continue

                    # Ampliación para facilitar OCR.
                    h, w = imagen_region.shape[:2]
                    escala = min(3.0, max(1.0, 600 / max(w, 1)))

                    ampliada = cv2.resize(
                        imagen_region,
                        None,
                        fx=escala,
                        fy=escala,
                        interpolation=cv2.INTER_CUBIC
                    )

                    nombre = (
                        f"track_{track_id}_"
                        f"frame_{frame}_"
                        f"muestra_{posicion}_"
                        f"{region}.jpg"
                    )

                    ruta = carpeta / nombre

                    if not cv2.imwrite(str(ruta), ampliada):
                        errores += 1
                        continue

                    solicitud = json.dumps(
                        {"imagen": str(ruta)},
                        ensure_ascii=False
                    )

                    try:
                        if proceso.poll() is not None:
                            raise RuntimeError(
                                "El proceso OCR terminó inesperadamente"
                            )

                        proceso.stdin.write(solicitud + "\n")
                        proceso.stdin.flush()

                        respuesta = proceso.stdout.readline()

                        if not respuesta:
                            raise RuntimeError(
                                "El proceso OCR no devolvió respuesta"
                            )

                        datos = json.loads(respuesta)
                        intentos += 1

                        for lectura in datos.get("lecturas", []):
                            texto = str(
                                lectura.get("texto", "")
                            ).strip()

                            confianza = float(
                                lectura.get("confianza", 0)
                            )

                            if not texto:
                                continue

                            registros.append({
                                "track_id": track_id,
                                "clase": clase,
                                "fotograma": frame,
                                "region": region,
                                "texto": texto,
                                "confianza": round(confianza, 3),
                                "archivo": nombre,
                                "estado": "PENDIENTE_REVISION"
                            })

                    except (
                        OSError,
                        ValueError,
                        json.JSONDecodeError,
                        RuntimeError
                    ) as exc:
                        errores += 1
                        print(
                            "ERROR OCR:",
                            track_id,
                            frame,
                            str(exc),
                            flush=True
                        )

                        if proceso.poll() is not None:
                            raise RuntimeError(
                                "El worker OCR ha dejado de funcionar"
                            ) from exc

    finally:
        if proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait()

    ruta_csv = carpeta / "resultados.csv"

    with ruta_csv.open(
        "w", newline="", encoding="utf-8"
    ) as archivo:

        campos = [
            "track_id", "clase", "fotograma",
            "region", "texto", "confianza",
            "archivo", "estado"
        ]

        escritor = csv.DictWriter(
            archivo, fieldnames=campos
        )

        escritor.writeheader()
        escritor.writerows(registros)

    print("\n=== RESULTADOS OCR V4 ===")
    print("Intentos OCR:", intentos)
    print("Errores OCR:", errores)
    print("Textos candidatos:", len(registros))

    print("\n=== MEJORES LECTURAS ===")

    for fila in sorted(
        registros,
        key=lambda x: x["confianza"],
        reverse=True
    )[:20]:
        print(
            f"Track {fila['track_id']} | "
            f"{fila['texto']} | "
            f"conf={fila['confianza']:.2f} | "
            f"{fila['region']}"
        )

    print("\nResultados:", ruta_csv)
    print("Imágenes:", carpeta)
    print("Todas las lecturas requieren revisión.")
    print("No se generaron alertas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--video", required=True)
    parser.add_argument("--fps", type=float, default=3)
    parser.add_argument("--mejores", type=int, default=3)

    args = parser.parse_args()

    if args.fps <= 0 or args.mejores < 1:
        parser.error("Los parámetros deben ser positivos")

    ejecutar(
        Path(args.video),
        args.fps,
        args.mejores
    )
