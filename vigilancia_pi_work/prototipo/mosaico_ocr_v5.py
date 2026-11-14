from pathlib import Path
import csv
import cv2
import numpy as np

CARPETA = (
    Path.home() / "vigilancia" / "prototipo"
    / "datos" / "banco_ocr_v4" / "matriculas_prueba"
)

with (CARPETA / "resultados.csv").open(
    encoding="utf-8", newline=""
) as f:
    filas = list(csv.DictReader(f))

vistos = set()
imagenes = []

for fila in filas:
    nombre = fila["archivo"]

    if nombre in vistos:
        continue

    vistos.add(nombre)
    imagen = cv2.imread(str(CARPETA / nombre))

    if imagen is None:
        continue

    ancho, alto = 480, 300
    h, w = imagen.shape[:2]

    escala = min(ancho / w, (alto - 40) / h)
    nuevo = cv2.resize(
        imagen,
        (max(1, int(w * escala)), max(1, int(h * escala)))
    )

    lienzo = np.full((alto, ancho, 3), 35, dtype=np.uint8)
    y = 40 + (alto - 40 - nuevo.shape[0]) // 2
    x = (ancho - nuevo.shape[1]) // 2

    lienzo[y:y + nuevo.shape[0], x:x + nuevo.shape[1]] = nuevo

    etiqueta = (
        f"Track {fila['track_id']} | "
        f"Frame {fila['fotograma']} | {fila['region']}"
    )

    cv2.putText(
        lienzo, etiqueta, (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55, (255, 255, 255), 1,
        cv2.LINE_AA
    )

    imagenes.append(lienzo)

if not imagenes:
    raise SystemExit("No hay imágenes para el mosaico")

columnas = 3
filas_total = (len(imagenes) + columnas - 1) // columnas

vacio = np.full((300, 480, 3), 35, dtype=np.uint8)

while len(imagenes) < filas_total * columnas:
    imagenes.append(vacio.copy())

filas_mosaico = []

for i in range(0, len(imagenes), columnas):
    filas_mosaico.append(
        np.hstack(imagenes[i:i + columnas])
    )

mosaico = np.vstack(filas_mosaico)
ruta = CARPETA / "mosaico_v5.jpg"

cv2.imwrite(str(ruta), mosaico)

print("Mosaico creado:", ruta)
print("Imágenes incluidas:", len(vistos))
