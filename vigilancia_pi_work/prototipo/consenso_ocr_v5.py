#!/usr/bin/env python3

from pathlib import Path
from collections import defaultdict, Counter
import csv
import json
import re

BASE = Path.home() / "vigilancia"
CARPETA = (
    BASE / "prototipo" / "datos"
    / "banco_ocr_v4" / "matriculas_prueba"
)

CSV = CARPETA / "resultados.csv"
SALIDA = CARPETA / "consenso_v5.json"


def normalizar(texto):
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def distancia(a, b):
    """Distancia de edición entre dos cadenas."""
    anterior = list(range(len(b) + 1))

    for i, ca in enumerate(a, 1):
        actual = [i]

        for j, cb in enumerate(b, 1):
            actual.append(min(
                actual[-1] + 1,
                anterior[j] + 1,
                anterior[j - 1] + (ca != cb)
            ))

        anterior = actual

    return anterior[-1]


def analizar():
    if not CSV.is_file():
        raise FileNotFoundError(CSV)

    grupos = defaultdict(list)

    with CSV.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            fila["normalizado"] = normalizar(fila["texto"])
            fila["confianza"] = float(fila["confianza"])
            fila["fotograma"] = int(fila["fotograma"])

            if fila["normalizado"]:
                grupos[int(fila["track_id"])].append(fila)

    resultados = []

    print("\n=== CONSENSO TEMPORAL OCR V5 ===")

    for track_id, filas in sorted(grupos.items()):

        # Para cada texto, contamos fotogramas únicos.
        votos = defaultdict(set)
        confianza_por_texto = defaultdict(list)

        for fila in filas:
            texto = fila["normalizado"]
            votos[texto].add(fila["fotograma"])
            confianza_por_texto[texto].append(fila["confianza"])

        # Orden: mayor número de fotogramas, después confianza.
        candidatos = sorted(
            votos,
            key=lambda texto: (
                len(votos[texto]),
                sum(confianza_por_texto[texto])
                / len(confianza_por_texto[texto])
            ),
            reverse=True
        )

        principal = candidatos[0]

        alternativas = []

        for texto in candidatos[1:]:
            alternativas.append({
                "texto": texto,
                "fotogramas": len(votos[texto]),
                "distancia_al_principal": distancia(principal, texto)
            })

        fotogramas_principal = len(votos[principal])
        confianza_media = (
            sum(confianza_por_texto[principal])
            / len(confianza_por_texto[principal])
        )

        # No significa que sea una matrícula verificada.
        consenso = (
            "REPETIDO_EN_VARIOS_FOTOGRAMAS"
            if fotogramas_principal >= 2
            else "EVIDENCIA_INSUFICIENTE"
        )

        resultado = {
            "track_id": track_id,
            "texto_principal": principal,
            "fotogramas_distintos": fotogramas_principal,
            "confianza_ocr_media": round(confianza_media, 3),
            "consenso": consenso,
            "alternativas": alternativas,
            "estado": "PENDIENTE_REVISION_VISUAL",
            "matricula_verificada": False
        }

        resultados.append(resultado)

        print(f"\nTRACK {track_id}")
        print("  Texto principal:", principal)
        print("  Fotogramas distintos:", fotogramas_principal)
        print("  Confianza media OCR:", round(confianza_media, 3))
        print("  Consenso:", consenso)

        for alt in alternativas:
            print(
                "  Alternativa:",
                alt["texto"],
                "| fotogramas:", alt["fotogramas"],
                "| distancia:", alt["distancia_al_principal"]
            )

    # Comprobación de textos compartidos entre tracks.
    compartidos = defaultdict(list)

    for resultado in resultados:
        compartidos[resultado["texto_principal"]].append(
            resultado["track_id"]
        )

    print("\n=== TEXTOS COMPARTIDOS ENTRE TRACKS ===")

    for texto, tracks in compartidos.items():
        if len(tracks) > 1:
            print(
                texto,
                "aparece en tracks",
                tracks,
                "- requiere comprobar si es el mismo vehículo "
                "o texto superpuesto en el vídeo"
            )

    informe = {
        "archivo_origen": str(CSV),
        "resultados": resultados,
        "textos_compartidos": {
            texto: tracks
            for texto, tracks in compartidos.items()
            if len(tracks) > 1
        },
        "alertas_generadas": 0,
        "nota": (
            "Consenso OCR no equivale a matrícula verificada. "
            "Revisar visualmente las imágenes originales."
        )
    }

    SALIDA.write_text(
        json.dumps(informe, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("\n=== RESUMEN ===")
    print("Tracks con OCR:", len(resultados))
    print(
        "Tracks con texto repetido:",
        sum(
            x["fotogramas_distintos"] >= 2
            for x in resultados
        )
    )
    print("Matrículas verificadas: 0")
    print("Alertas generadas: 0")
    print("Informe:", SALIDA)


if __name__ == "__main__":
    analizar()
