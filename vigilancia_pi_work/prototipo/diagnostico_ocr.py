from pathlib import Path
import sqlite3
import cv2
from ultralytics import YOLO

BASE = Path.home() / "vigilancia"
DB = BASE / "prototipo" / "datos" / "demo.db"
VIDEO = BASE / "videos" / "trafico_prueba.mp4"
MODELO = BASE / "modelos" / "yolo26n_ncnn_model"

print("\n=== 1. DETECCIONES REGISTRADAS ===")

con = sqlite3.connect(DB)

for tipo, cantidad in con.execute(
    """
    SELECT tipo, COUNT(*)
    FROM objetos
    GROUP BY tipo
    ORDER BY COUNT(*) DESC
    """
):
    print(f"{tipo}: {cantidad}")

print("\n=== 2. VEHÍCULOS Y TAMAÑOS DE RECORTE ===")

modelo = YOLO(str(MODELO))
cap = cv2.VideoCapture(str(VIDEO))

fps = cap.get(cv2.CAP_PROP_FPS)
paso = max(1, round(fps / 5))
indice = 0

vehiculos = {"car", "truck", "bus", "motorcycle"}
total_vehiculos = 0
recortes_validos = 0

while True:
    correcto, imagen = cap.read()
    if not correcto:
        break

    if indice % paso == 0:
        resultado = modelo.predict(
            source=imagen,
            imgsz=640,
            device="cpu",
            verbose=False
        )[0]

        for caja in resultado.boxes:
            clase = resultado.names[int(caja.cls[0])]
            confianza = float(caja.conf[0])

            if clase not in vehiculos:
                continue

            total_vehiculos += 1

            x1, y1, x2, y2 = map(
                int, caja.xyxy[0].tolist()
            )

            ancho = x2 - x1
            alto = y2 - y1

            valido = (
                confianza >= 0.55
                and ancho >= 80
                and alto >= 40
            )

            if valido:
                recortes_validos += 1

            if total_vehiculos <= 20:
                print(
                    f"{clase:12s} "
                    f"conf={confianza:.2f} "
                    f"tamaño={ancho}x{alto} "
                    f"OCR={'SI' if valido else 'NO'}"
                )

    indice += 1

cap.release()
con.close()

print("\n=== RESUMEN ===")
print("Detecciones de vehículos:", total_vehiculos)
print("Recortes que cumplen condiciones OCR:", recortes_validos)

if recortes_validos == 0:
    print("CAUSA PROBABLE: filtros demasiado restrictivos.")
else:
    print("Existen recortes válidos: revisar selección por track_id y comunicación OCR.")
