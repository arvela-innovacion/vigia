from pathlib import Path
from collections import defaultdict
import argparse
import csv
import cv2
import numpy as np
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR

BASE = Path.home() / "vigilancia"
MODELO = BASE / "modelos" / "yolo26n_ncnn_model"
VEHICULOS = {"car", "truck", "bus", "motorcycle"}


def nitidez(imagen):
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gris, cv2.CV_64F).var())


def variantes(imagen):
    alto, ancho = imagen.shape[:2]

    escala = min(3.0, max(1.0, 600 / max(ancho, 1)))
    grande = cv2.resize(
        imagen, None, fx=escala, fy=escala,
        interpolation=cv2.INTER_CUBIC
    )

    gris = cv2.cvtColor(grande, cv2.COLOR_BGR2GRAY)
    contraste = cv2.createCLAHE(
        clipLimit=2.0, tileGridSize=(8, 8)
    ).apply(gris)

    return {
        "original": imagen,
        "ampliada": grande,
        "contraste": contraste
    }


def ejecutar(video, fps_objetivo, max_candidatos):
    salida = BASE / "prototipo" / "datos" / "banco_ocr_v4" / video.stem
    salida.mkdir(parents=True, exist_ok=True)

    detector = YOLO(str(MODELO))
    ocr = RapidOCR()

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"No se puede abrir: {video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    paso = max(1, round(fps / fps_objetivo))

    candidatos = defaultdict(list)
    fotograma = 0
    vehiculos = 0

    print("Analizando vídeo:", video)

    while True:
        ok, imagen = cap.read()
        if not ok:
            break

        if fotograma % paso != 0:
            fotograma += 1
            continue

        resultado = detector.track(
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

                vehiculos += 1

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
                calidad = nitidez(recorte)

                # Combinamos nitidez y tamaño, sin asumir que
                # el vehículo contiene una matrícula legible.
                puntuacion = (
                    min(calidad, 500.0) *
                    min(recorte.shape[1], 500) *
                    min(recorte.shape[0], 500)
                )

                clave = (clase, track_id)
                candidatos[clave].append(
                    (puntuacion, fotograma, recorte)
                )

                candidatos[clave].sort(
                    key=lambda x: x[0], reverse=True
                )

                candidatos[clave] = candidatos[clave][:max_candidatos]

        fotograma += 1

    cap.release()

    registros = []
    total_textos = 0

    print("\nVehículos detectados (observaciones):", vehiculos)
    print("Tracks con recortes:", len(candidatos))
    print("\nEjecutando OCR...")

    for (clase, track_id), muestras in candidatos.items():
        for indice, (_, frame, recorte) in enumerate(muestras):
            nombre = f"{clase}_{track_id}_f{frame}_{indice}"
            cv2.imwrite(str(salida / f"{nombre}.jpg"), recorte)

            for nombre_variante, imagen in variantes(recorte).items():
                try:
                    resultado, _ = ocr(imagen)
                except Exception as exc:
                    print("Error OCR:", exc)
                    continue

                for lectura in resultado or []:
                    texto = str(lectura[1]).strip()
                    confianza = float(lectura[2])

                    if not texto:
                        continue

                    total_textos += 1
                    registros.append({
                        "clase": clase,
                        "track_id": track_id,
                        "fotograma": frame,
                        "variante": nombre_variante,
                        "texto": texto,
                        "confianza": round(confianza, 3),
                        "archivo": f"{nombre}.jpg",
                        "estado": "PENDIENTE_REVISION"
                    })

    ruta_csv = salida / "candidatos_ocr.csv"

    with ruta_csv.open("w", newline="", encoding="utf-8") as f:
        campos = [
            "clase", "track_id", "fotograma", "variante",
            "texto", "confianza", "archivo", "estado"
        ]
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(registros)

    print("\n=== RESULTADOS OCR V4 ===")
    print("Tracks analizados:", len(candidatos))
    print("Textos OCR candidatos:", total_textos)

    for fila in sorted(
        registros,
        key=lambda x: x["confianza"],
        reverse=True
    )[:20]:
        print(
            f"Track {fila['track_id']} | "
            f"{fila['texto']} | "
            f"conf={fila['confianza']:.2f} | "
            f"{fila['variante']}"
        )

    print("\nRecortes y CSV:", salida)
    print("Ningún texto se ha validado como matrícula.")
    print("No se han generado alertas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--fps", type=float, default=3)
    parser.add_argument("--max-candidatos", type=int, default=3)
    args = parser.parse_args()

    if args.fps <= 0 or args.max_candidatos < 1:
        parser.error("FPS y número de candidatos deben ser positivos")

    ejecutar(
        Path(args.video),
        args.fps,
        args.max_candidatos
    )
