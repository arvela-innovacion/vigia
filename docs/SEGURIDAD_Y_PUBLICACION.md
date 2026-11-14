# Checklist de seguridad antes de publicar

- [ ] Repo configurado como **privado** (verificar en GitHub).
- [ ] Estructura raíz: `prototipo/`, `README.md`, `.gitignore`, `.env.example`; no carpeta `vigilancia_pi_work/` intermedia.
- [ ] No hay `.env` real, tokens, contraseñas, claves SSH, archivos `.pem` o `.key`.
- [ ] No hay bases SQLite reales, vídeos, modelos, logs ni backups.
- [ ] No hay contraseñas en URLs RTSP o HTTP.
- [ ] No hay credenciales en historial de Git, commits anteriores o archivos borrados de la rama actual.
- [ ] El token de Telegram compartido anteriormente se ha rotado.
- [ ] Los reportes `pip freeze` se han inspeccionado por URLs privadas con credenciales.
- [ ] Los ejemplos de datos OCR no se presentan como matrículas verificadas.
- [ ] Las alertas críticas se etiquetan como **simuladas**.
- [ ] Revisar manualmente el contenido del ZIP antes de compartirlo con Work.

## Variables previstas
```dotenv
VIG_TELEGRAM_TOKEN=
VIG_TELEGRAM_CHAT_ID=
VIG_RTSP_USER=
VIG_RTSP_PASSWORD=
```
Las variables RTSP son propuestas, no integración confirmada.

## Advertencia
Un `.gitignore` no protege archivos que ya fueron versionados. Si un secreto entró en un commit, hay que revocarlo/rotarlo y evaluar limpieza del historial; borrar el archivo en un commit nuevo no basta.
