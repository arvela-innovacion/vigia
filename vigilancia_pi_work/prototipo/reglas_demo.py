from pathlib import Path
from datetime import datetime
import argparse
import json
import re
import sqlite3

BASE = Path.home() / "vigilancia" / "prototipo"
DB = BASE / "datos" / "demo.db"
DB.parent.mkdir(parents=True, exist_ok=True)

EJEMPLOS = [
    ("matricula", "1234BCF", "negra", "Vehículo de prueba A"),
    ("matricula", "5678DEF", "blanca", "Vehículo autorizado de prueba"),
    ("matricula", "TEST999", "negra", "Vehículo de prueba B"),
    ("persona_demo", "DEMO-P001", "negra", "Persona ficticia de prueba A"),
    ("persona_demo", "DEMO-P002", "blanca", "Persona ficticia autorizada"),
]


def ahora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalizar(tipo, identificador):
    texto = str(identificador).strip().upper()
    if tipo == "matricula":
        return re.sub(r"[^A-Z0-9]", "", texto)
    return texto


def conectar():
    conexion = sqlite3.connect(DB, timeout=15)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys=ON")
    conexion.execute("PRAGMA busy_timeout=15000")
    return conexion


def preparar():
    with conectar() as db:
        db.executescript("""
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

            CREATE TABLE IF NOT EXISTS evaluaciones_demo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creada TEXT NOT NULL,
                tipo TEXT NOT NULL,
                identificador TEXT NOT NULL,
                confianza REAL NOT NULL,
                verificado INTEGER NOT NULL,
                origen TEXT NOT NULL,
                resultado TEXT NOT NULL,
                detalle TEXT NOT NULL,
                alerta_id INTEGER,
                FOREIGN KEY(alerta_id) REFERENCES alertas(id)
            );
        """)

        # Los ejemplos se cargan solamente si no existen.
        # No reemplazamos las decisiones hechas desde el panel.
        for tipo, identificador, lista, descripcion in EJEMPLOS:
            db.execute(
                """INSERT OR IGNORE INTO listas
                   (tipo, identificador, lista, descripcion)
                   VALUES (?, ?, ?, ?)""",
                (tipo, identificador, lista, descripcion)
            )


def evaluar(tipo, identificador, confianza=1.0,
            verificado=False, origen="manual_demo"):
    if tipo not in ("matricula", "persona_demo"):
        raise ValueError("Tipo no permitido")

    identificador = normalizar(tipo, identificador)
    if not identificador or len(identificador) > 64:
        raise ValueError("Identificador vacío o demasiado largo")

    confianza = float(confianza)
    if not 0 <= confianza <= 1:
        raise ValueError("Confianza fuera de rango")

    if origen not in ("manual_demo", "ocr_candidato"):
        raise ValueError("Origen no permitido")

    # Un resultado OCR no puede marcarse como verificado por
    # esta interfaz: necesita un proceso de revisión independiente.
    if origen == "ocr_candidato":
        verificado = False

    with conectar() as db:
        entrada = db.execute(
            """SELECT lista, descripcion FROM listas
               WHERE tipo=? AND identificador=?""",
            (tipo, identificador)
        ).fetchone()

        alerta_id = None

        if not verificado or confianza < 0.85:
            resultado = "REVISION"
            detalle = "Identificación no verificada o confianza insuficiente"
        elif entrada is None:
            resultado = "DESCONOCIDO"
            detalle = "No existe coincidencia en las listas de demostración"
        elif entrada["lista"] == "blanca":
            resultado = "CONOCIDO_OK"
            detalle = "Coincidencia ficticia con lista blanca"
        elif entrada["lista"] == "negra":
            resultado = "CRITICO_ALERTA"
            detalle = "Coincidencia ficticia con lista negra"

            cursor = db.execute(
                """INSERT INTO alertas
                   (objeto_id, motivo, estado, creada, simulada)
                   VALUES (NULL, ?, 'pendiente', ?, 1)""",
                (
                    f"DEMO CRÍTICO: {tipo} {identificador}. "
                    "Coincidencia simulada. Revisión humana obligatoria.",
                    ahora()
                )
            )
            alerta_id = cursor.lastrowid
        else:
            resultado = "REVISION"
            detalle = "Estado de lista no reconocido"

        cursor = db.execute(
            """INSERT INTO evaluaciones_demo
               (creada, tipo, identificador, confianza,
                verificado, origen, resultado, detalle, alerta_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ahora(), tipo, identificador, confianza,
                int(bool(verificado)), origen,
                resultado, detalle, alerta_id
            )
        )

        return {
            "evaluacion_id": cursor.lastrowid,
            "tipo": tipo,
            "identificador": identificador,
            "resultado": resultado,
            "detalle": detalle,
            "alerta_id": alerta_id,
            "simulacion": True
        }


def guardar_lista(tipo, identificador, lista, descripcion=""):
    if tipo not in ("matricula", "persona_demo"):
        raise ValueError("Tipo no permitido")
    if lista not in ("blanca", "negra"):
        raise ValueError("Lista no permitida")

    identificador = normalizar(tipo, identificador)
    if not identificador or len(identificador) > 64:
        raise ValueError("Identificador no válido")

    with conectar() as db:
        db.execute(
            """INSERT INTO listas
               (tipo, identificador, lista, descripcion)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(tipo, identificador)
               DO UPDATE SET lista=excluded.lista,
                             descripcion=excluded.descripcion""",
            (tipo, identificador, lista, descripcion[:200])
        )


def prueba_completa():
    casos = [
        ("matricula", "1234BCF", 0.99, True, "manual_demo"),
        ("matricula", "5678DEF", 0.99, True, "manual_demo"),
        ("matricula", "TEST999", 0.98, True, "manual_demo"),
        ("persona_demo", "DEMO-P001", 1.0, True, "manual_demo"),
        ("persona_demo", "DEMO-P002", 1.0, True, "manual_demo"),
        ("matricula", "9999ZZZ", 0.99, True, "manual_demo"),
        ("matricula", "1234BCF", 0.61, False, "ocr_candidato"),
    ]

    print("\n=== PRUEBA INTEGRAL DE REGLAS ===")

    for tipo, identificador, confianza, verificado, origen in casos:
        resultado = evaluar(
            tipo, identificador, confianza, verificado, origen
        )
        print(
            f"{tipo:13s} {identificador:12s} "
            f"=> {resultado['resultado']:16s} "
            f"alerta={resultado['alerta_id']}"
        )

    with conectar() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM evaluaciones_demo"
        ).fetchone()[0]
        alertas = db.execute(
            "SELECT COUNT(*) FROM alertas WHERE simulada=1"
        ).fetchone()[0]

    print("\nEvaluaciones acumuladas:", total)
    print("Alertas simuladas acumuladas:", alertas)
    print("Base de datos:", DB)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probar", action="store_true")
    args = parser.parse_args()

    preparar()
    if args.probar:
        prueba_completa()
    else:
        print("Motor de reglas preparado.")
