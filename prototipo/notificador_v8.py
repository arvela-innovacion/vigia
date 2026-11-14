#!/usr/bin/env python3
import argparse
import json
import os
import smtplib
import sqlite3
import ssl
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

DB = Path.home() / "vigilancia/prototipo/datos/demo.db"


def ahora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def conectar():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=20000")
    return db


def preparar():
    with conectar() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS notificaciones_v8 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT NOT NULL,
                canal TEXT NOT NULL,
                nivel TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                intentos INTEGER NOT NULL DEFAULT 0,
                ultimo_error TEXT,
                creado TEXT NOT NULL,
                enviado TEXT,
                UNIQUE(clave, canal)
            )
        """)


def encolar(clave, canal, mensaje, nivel="CRITICO"):
    if canal not in ("telegram", "email"):
        raise ValueError("Canal no admitido")
    if nivel != "CRITICO":
        raise ValueError("Este módulo solo notifica eventos CRITICOS")

    with conectar() as db:
        cursor = db.execute("""
            INSERT OR IGNORE INTO notificaciones_v8
            (clave, canal, nivel, mensaje, creado)
            VALUES (?, ?, ?, ?, ?)
        """, (clave, canal, nivel, mensaje, ahora()))

    return cursor.rowcount == 1


def enviar_telegram(mensaje):
    token = os.environ["VIG_TELEGRAM_TOKEN"]
    chat_id = os.environ["VIG_TELEGRAM_CHAT_ID"]

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    datos = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": mensaje
    }).encode()

    peticion = urllib.request.Request(
        url, data=datos, method="POST"
    )

    with urllib.request.urlopen(peticion, timeout=15) as r:
        respuesta = json.load(r)

    if not respuesta.get("ok"):
        raise RuntimeError("Telegram no confirmó el envío")


def enviar_email(mensaje):
    servidor = os.environ["VIG_SMTP_HOST"]
    puerto = int(os.environ.get("VIG_SMTP_PORT", "465"))
    usuario = os.environ["VIG_SMTP_USER"]
    password = os.environ["VIG_SMTP_PASSWORD"]
    destinatario = os.environ["VIG_EMAIL_DESTINO"]

    correo = EmailMessage()
    correo["From"] = usuario
    correo["To"] = destinatario
    correo["Subject"] = "[VIGILANCIA DEMO] Evento CRITICO"
    correo.set_content(mensaje)

    contexto = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        servidor, puerto, context=contexto, timeout=15
    ) as smtp:
        smtp.login(usuario, password)
        smtp.send_message(correo)


def procesar():
    with conectar() as db:
        filas = db.execute("""
            SELECT *
            FROM notificaciones_v8
            WHERE estado IN ('pendiente', 'error')
              AND intentos < 5
            ORDER BY id
        """).fetchall()

    print(f"Notificaciones por procesar: {len(filas)}")

    for fila in filas:
        try:
            if fila["canal"] == "telegram":
                enviar_telegram(fila["mensaje"])
            elif fila["canal"] == "email":
                enviar_email(fila["mensaje"])

            with conectar() as db:
                db.execute("""
                    UPDATE notificaciones_v8
                    SET estado='enviado',
                        intentos=intentos+1,
                        ultimo_error=NULL,
                        enviado=?
                    WHERE id=?
                """, (ahora(), fila["id"]))

            print(f"ENVIADO id={fila['id']} canal={fila['canal']}")

        except Exception as exc:
            # Nunca guardar contraseñas ni tokens en la BBDD.
            error = type(exc).__name__

            with conectar() as db:
                db.execute("""
                    UPDATE notificaciones_v8
                    SET estado='error',
                        intentos=intentos+1,
                        ultimo_error=?
                    WHERE id=?
                """, (error, fila["id"]))

            print(
                f"ERROR id={fila['id']} "
                f"canal={fila['canal']} tipo={error}"
            )


def listar():
    with conectar() as db:
        filas = db.execute("""
            SELECT id, clave, canal, nivel,
                   estado, intentos, ultimo_error, enviado
            FROM notificaciones_v8
            ORDER BY id DESC
            LIMIT 30
        """).fetchall()

    for fila in filas:
        print(dict(fila))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--preparar", action="store_true")
    p.add_argument("--prueba", choices=["telegram", "email"])
    p.add_argument("--procesar", action="store_true")
    p.add_argument("--listar", action="store_true")
    args = p.parse_args()

    preparar()

    if args.prueba:
        clave = "DEMO-" + uuid.uuid4().hex[:12]
        mensaje = (
            "🚨 EVENTO CRITICO - SIMULACION\n"
            f"Referencia: {clave}\n"
            "Tipo: matrícula ficticia de prueba\n"
            "Estado: confirmado manualmente (simulado)\n"
            "Acción: revisar el evento en el prototipo.\n"
            "NO ES UNA ALERTA POLICIAL REAL."
        )
        creado = encolar(clave, args.prueba, mensaje)
        print("Prueba encolada:", creado, clave)

    if args.procesar:
        procesar()

    if args.listar:
        listar()

    if not any((
        args.preparar, args.prueba,
        args.procesar, args.listar
    )):
        p.print_help()


if __name__ == "__main__":
    main()
