# VIGIA — Arquitectura y estado técnico

## Visión general
```text
Vídeo MP4 [validado en pruebas] / cámara RTSP [pendiente]
    ↓
Detección YOLO26n + NCNN
    ↓
Seguimiento ByteTrack
    ↓
RapidOCR
    ↓
Candidatos OCR / consenso
    ↓
SQLite
    ↓
Revisión humana (verificar/rechazar)
    ↓
Reglas ficticias de demostración
    ↓
Alertas simuladas / notificación Telegram
```

**Separar dos rutas:**
- `ejecutar_video_telegram_v11.py`: vídeo → resumen informativo directo a Telegram, probado.
- `alertas_telegram_v9.py` + revisión + reglas + notificador: ruta de alertas críticas simuladas, **no validada íntegramente**.

## Principios invariantes
1. OCR = hipótesis; no evidencia concluyente de matrícula.
2. Una coincidencia en una lista ficticia no es un registro policial.
3. Alertas críticas solo después de verificación humana, según las reglas que confirme el código.
4. Mantener trazabilidad de sesiones, candidatos, revisiones, decisiones y envíos.
5. No almacenar ni compartir tokens o contraseñas en Git.
6. Mantener los módulos existentes hasta que sus reemplazos pasen pruebas.

## Mapa de módulos
| Módulo | Función | Estado histórico |
|---|---|---|
| `motor_ocr_v5.py` | Procesamiento OCR de vídeo | Utilizado |
| `consolidar_ocr_db.py` | Consolidar candidatos | Revisar CLI y rutas hardcodeadas |
| `revision_ocr_v6.py` | Revisión humana e informes | Utilizado |
| `reglas_demo.py` | Reglas ficticias | Implementado; validar integración |
| `notificador_v8.py` | Telegram / cola | Prueba Telegram correcta |
| `alertas_telegram_v9.py` | Alertas simuladas | Pendiente prueba end-to-end |
| `vigilancia_v10.py` | Orquestación | Parcial |
| `ejecutar_ocr_v7.py` | Ejecutor OCR | Probado |
| `ejecutar_video_telegram_v11.py` | MP4 + resumen Telegram | Probado |

## Dependencias a confirmar
Python 3.13.5, bibliotecas de detección/NCNN, ByteTrack, RapidOCR, SQLite (biblioteca estándar), integración HTTP de Telegram. **No asignar versiones de paquetes sin `pip freeze`, `pip list` y análisis de imports en los entornos reales.** Algunas librerías pueden proceder de repositorios Git o wheels ARM64 especiales.

## Pruebas que faltan
- Instalación desde cero con dependencias fijadas.
- Prueba automática de OCR con fixtures anonimizados o sintéticos.
- Prueba de consolidación y persistencia SQLite.
- Prueba de validación humana, rechazo y reglas.
- Prueba end-to-end de alerta crítica simulada, con credenciales de prueba o cliente Telegram simulado.
- Recuperación de red, pérdida de RTSP y reinicio del proceso.
- Rendimiento sostenido en Raspberry Pi 5: FPS, CPU, RAM, temperatura y latencia.

## Contexto de conectividad
Tailscale permite SSH entre redes distintas si ambos dispositivos tienen Internet y el servicio está activo. Hubo una incidencia por cambio de Wi-Fi: se usó temporalmente un hotspot con SSID/contraseña conocidos, y se preparó un perfil para una nueva red. No confundir disponibilidad de Tailscale con confirmación de la Wi-Fi actual. Nunca incluir contraseñas Wi-Fi en documentación o Git.
