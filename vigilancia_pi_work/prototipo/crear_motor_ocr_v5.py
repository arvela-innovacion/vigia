from pathlib import Path

carpeta = Path.home() / "vigilancia" / "prototipo"
origen = carpeta / "banco_ocr_v4b.py"
destino = carpeta / "motor_ocr_v5.py"

texto = origen.read_text(encoding="utf-8")

# Importamos el módulo SQLite.
texto = texto.replace(
    "from ultralytics import YOLO",
    "from ultralytics import YOLO\n"
    "from ocr_db import preparar, crear_sesion, "
    "guardar_lectura, cerrar_sesion, mostrar"
)

# Creamos sesión OCR al comenzar.
texto = texto.replace(
    "    modelo = YOLO(str(MODELO))",
    "    preparar()\n"
    "    sesion_db = crear_sesion(video)\n"
    "    modelo = YOLO(str(MODELO))"
)

# Guardamos cada lectura en SQLite al recibirla.
buscado = """                            registros.append({
                                "track_id": track_id,"""

reemplazo = """                            guardar_lectura(
                                sesion_db,
                                track_id,
                                clase,
                                frame,
                                region,
                                texto,
                                confianza,
                                ruta
                            )

                            registros.append({
                                "track_id": track_id,"""

if buscado not in texto:
    raise SystemExit(
        "No coincide el código V4 esperado. "
        "No se ha generado el motor V5."
    )

texto = texto.replace(buscado, reemplazo, 1)

# No necesitamos generar un CSV nuevo.
inicio = texto.index("    ruta_csv = carpeta / \"resultados.csv\"")
fin = texto.index("    print(\"\\n=== RESULTADOS OCR V4 ===\")", inicio)

texto = (
    texto[:inicio]
    + "    cerrar_sesion(\n"
      "        sesion_db,\n"
      "        fotogramas=analizados,\n"
      "        intentos=intentos,\n"
      "        errores=errores\n"
      "    )\n\n"
    + texto[fin:]
)

texto = texto.replace(
    '    print("\\nResultados:", ruta_csv)',
    '    print("\\nSesión SQLite:", sesion_db)\n'
    '    mostrar(sesion_db)'
)

destino.write_text(texto, encoding="utf-8")

print("Motor creado:", destino)
print("Motor V4 original conservado.")
