import json
import sys

from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()

for linea in sys.stdin:
    try:
        peticion = json.loads(linea)
        resultado, _ = ocr(peticion["imagen"])
        lecturas = []

        for elemento in resultado or []:
            caja, texto, confianza = elemento
            lecturas.append({
                "texto": str(texto),
                "confianza": float(confianza)
            })

        print(json.dumps({"lecturas": lecturas}), flush=True)

    except Exception as exc:
        print(json.dumps({"error": str(exc)}), flush=True)
