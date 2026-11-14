# Plan de desarrollo incremental

## Etapa A — Auditoría del repositorio
- Listar árbol real y detectar rutas/archivos faltantes.
- Confirmar `README.md`, `.gitignore`, `.env.example` en raíz.
- Verificar imports, CLI y versiones de cada módulo.
- Identificar rutas absolutas, nombres de vídeos y esquemas SQLite fijados en código.
- Proponer cambios pequeños, con pruebas y rollback.

## Etapa B — Reproducibilidad
- Inventariar ambos entornos Python de la Raspberry.
- Crear `requirements.in` y lock/constraints verificados en ARM64.
- Documentar instalación de NCNN/modelo y scripts de smoke test.

## Etapa C — Robustez funcional
- Tests de candidatos, consolidación, revisión, reglas ficticias y notificación simulada.
- Prueba integral de `alertas_telegram_v9.py` sin emitir mensajes críticos no deseados.
- Separar notificaciones informativas de alertas críticas simuladas.
- Logging estructurado, errores claros y control de duplicados.

## Etapa D — Cámara Tapo C200
- Confirmar activación RTSP y credenciales locales seguras.
- Ingesta con reconexión y descarte de fotogramas antiguos.
- Detección de movimiento ligera y ROI antes de inferencia costosa.
- Control de FPS, cooldown, recursos y temperatura.
- Medir precisión con condiciones reales sin tratar OCR como verificación.

## Etapa E — Operación y documentación
- CI con pruebas que no dependan de hardware/secretos.
- Guías de despliegue y recuperación.
- Documentar retención de datos, seguridad, privacidad y limitaciones.
