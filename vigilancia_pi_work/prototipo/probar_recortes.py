from pathlib import Path
from rapidocr_onnxruntime import RapidOCR
import cv2

CARPETA = (
    Path.home()
    / "vigilancia/prototipo/datos/evidencias"
)

archivos = sorted(CARPETA.glob("*_objeto_*.jpg"))

print(f"Recortes encontrados: {len(archivos)}")

ocr = RapidOCR()
con_texto = 0

for archivo in archivos:
    imagen = cv2.imread(str(archivo))

    if imagen is None:
        print(f"{archivo.name}: ERROR AL ABRIR")
        continue

    alto, ancho = imagen.shape[:2]
    resultado, _ = ocr(imagen)

    textos = [
        (elemento[1], round(float(elemento[2]), 2))
        for elemento in (resultado or [])
    ]

    if textos:
        con_texto += 1

    print(
        f"{archivo.name} | {ancho}x{alto} | "
        f"{textos if textos else 'Sin texto'}"
    )

print("\n=== RESUMEN ===")
print("Recortes analizados:", len(archivos))
print("Recortes con texto:", con_texto)
