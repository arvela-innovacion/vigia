# VIGIA 👁️
### Sistema inteligente de vigilancia y reconocimiento de matrículas con Raspberry Pi 5

**VIGIA** es un proyecto de visión artificial desarrollado sobre **Raspberry Pi 5**, orientado a la detección de vehículos, el reconocimiento óptico de matrículas y la generación de eventos y notificaciones.

El sistema combina modelos de inteligencia artificial, seguimiento de objetos, OCR, almacenamiento local y notificaciones mediante Telegram.

Su objetivo es construir una plataforma modular, eficiente y ampliable, capaz de procesar vídeo y, en futuras versiones, analizar imágenes de cámaras IP en tiempo real.

> **Estado del proyecto:** prototipo funcional en desarrollo. El procesamiento de vídeo y el envío de resúmenes a Telegram se han probado. La integración de cámaras RTSP y el flujo completo de alertas críticas siguen en desarrollo.

---

## 1. Objetivos del proyecto

VIGIA busca proporcionar una base técnica para:

- Detectar vehículos mediante visión artificial.
- Realizar seguimiento de objetos entre fotogramas.
- Extraer posibles matrículas mediante reconocimiento óptico de caracteres.
- Consolidar varias lecturas OCR para reducir errores.
- Registrar resultados y eventos en una base de datos local.
- Permitir la revisión y validación humana de las lecturas.
- Evaluar matrículas verificadas contra listas ficticias de demostración.
- Generar notificaciones informativas mediante Telegram.
- Evolucionar hacia el procesamiento continuo de cámaras IP.

El proyecto prioriza la **modularidad, la trazabilidad de los resultados y la separación entre detecciones automáticas y decisiones verificadas**.

## 2. Arquitectura general

El flujo previsto del sistema es:

```text
Fuente de vídeo
    |
    v
Detección de objetos
YOLO + NCNN
    |
    v
Seguimiento
ByteTrack
    |
    v
Reconocimiento OCR
RapidOCR
    |
    v
Consolidación de candidatos
    |
    v
Base de datos SQLite
    |
    v
Revisión humana
    |
    v
Motor de reglas de demostración
    |
    +----> Eventos informativos
    |
    +----> Alertas críticas simuladas
                |
                v
          Notificaciones
             Telegram
```

**Importante:** las lecturas OCR automáticas son candidatos, no matrículas confirmadas. Las alertas críticas de demostración no representan coincidencias con bases de datos policiales ni registros oficiales.

## 3. Hardware

### Plataforma principal

| Componente | Descripción |
|---|---|
| Ordenador | Raspberry Pi 5 |
| Memoria RAM | 8 GB |
| Sistema operativo | Raspberry Pi OS Lite, 64 bits |
| Arquitectura | ARM64 / aarch64 |
| Almacenamiento | Almacenamiento local de la Raspberry |
| Conectividad | Wi-Fi, Ethernet y acceso remoto mediante Tailscale |

### Cámara IP

Está prevista la integración de una **TP-Link Tapo C200** mediante RTSP.

La cámara se utilizará como fuente de vídeo para sustituir o complementar los archivos MP4 empleados durante las pruebas.

La integración RTSP todavía no se considera validada.

## 4. Tecnologías

| Tecnología | Función |
|---|---|
| Python | Lenguaje principal |
| YOLO26n | Detección de objetos |
| NCNN | Inferencia optimizada para dispositivos ARM |
| ByteTrack | Seguimiento de objetos |
| RapidOCR | Reconocimiento óptico de caracteres |
| SQLite | Persistencia local |
| Telegram Bot API | Notificaciones |
| Tailscale | Acceso remoto privado |
| Git y GitHub | Control de versiones y colaboración |

El entorno de desarrollo utilizado incluye **Python 3.13** sobre Raspberry Pi OS Lite.

## 5. Estructura del repositorio

```text
vigia/
├── prototipo/
│   ├── motor_ocr_v5.py
│   ├── consolidar_ocr_db.py
│   ├── revision_ocr_v6.py
│   ├── reglas_demo.py
│   ├── notificador_v8.py
│   ├── alertas_telegram_v9.py
│   ├── vigilancia_v10.py
│   ├── ejecutar_ocr_v7.py
│   └── ejecutar_video_telegram_v11.py
│
├── .gitignore
├── .env.example
└── README.md
```

La estructura anterior representa los principales módulos conocidos del prototipo. Pueden existir otros archivos auxiliares.

Los entornos virtuales, vídeos de prueba, modelos, bases de datos y credenciales reales no se incluyen en el repositorio.

## 6. Componentes principales

### `motor_ocr_v5.py`

Motor de procesamiento OCR sobre vídeo.

Integra la detección y el seguimiento de objetos con el reconocimiento óptico de caracteres, generando lecturas candidatas para su posterior análisis.

### `consolidar_ocr_db.py`

Consolidación de lecturas OCR almacenadas.

Su función es agrupar resultados y facilitar la obtención de candidatos más consistentes.

**Estado:** módulo de prototipo con parámetros de entrada todavía parcialmente definidos en el código.

### `revision_ocr_v6.py`

Interfaz de línea de comandos para la revisión de candidatos.

Permite consultar lecturas pendientes, verificar manualmente una matrícula, rechazar candidatos y generar informes.

La validación humana es una parte fundamental del diseño.

### `reglas_demo.py`

Motor de reglas de demostración.

Utiliza listas blancas y negras ficticias para probar la lógica de clasificación y la generación de alertas simuladas.

No utiliza bases de datos policiales ni servicios oficiales.

### `notificador_v8.py`

Módulo de notificaciones.

Gestiona el envío de mensajes mediante Telegram y contempla operaciones de prueba, consulta y procesamiento de notificaciones.

### `alertas_telegram_v9.py`

Módulo experimental para relacionar las verificaciones manuales con las alertas críticas simuladas.

**Estado:** pendiente de validación integral del flujo.

### `vigilancia_v10.py`

Orquestación parcial de distintos componentes del prototipo.

**Estado:** en desarrollo.

### `ejecutar_ocr_v7.py`

Ejecutor de procesamiento OCR.

Se ha utilizado satisfactoriamente en pruebas con archivos de vídeo.

### `ejecutar_video_telegram_v11.py`

Ejecutor de vídeo con notificación informativa a Telegram.

Permite procesar un archivo MP4 y enviar un resumen de la sesión.

**Estado:** probado funcionalmente con vídeo local.

Este script no debe confundirse con el flujo completo de alertas críticas simuladas, que continúa en desarrollo.

## 7. Instalación y requisitos

El proyecto se ha desarrollado para Raspberry Pi OS Lite de 64 bits.

### Requisitos generales

- Raspberry Pi 5.
- Python 3.13 o entorno compatible, sujeto a validación.
- Entorno virtual de Python.
- Dependencias de detección, seguimiento y OCR.
- Modelo NCNN compatible.
- Archivo de vídeo de prueba o fuente de vídeo admitida.
- Conexión a Internet para utilizar Telegram.

### Obtener el código

```bash
git clone https://github.com/arvela-innovacion/vigia.git
cd vigia
```

### Preparar un entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Nota:** este repositorio todavía no incluye una instalación reproducible completamente documentada. Es necesario inventariar y fijar las dependencias antes de considerar estos pasos suficientes para desplegar el sistema desde cero.

En la Raspberry de desarrollo existen entornos específicos para los componentes del proyecto.

Los modelos de inferencia y los archivos de prueba deben proporcionarse por separado.

## 8. Configuración de variables de entorno

Las credenciales no deben almacenarse directamente en el código fuente ni subirse al repositorio.

El archivo `.env.example` documenta las variables previstas:

```dotenv
# Telegram
VIG_TELEGRAM_TOKEN=
VIG_TELEGRAM_CHAT_ID=

# Integración RTSP prevista
VIG_RTSP_USER=
VIG_RTSP_PASSWORD=
```

Las credenciales reales deben configurarse mediante variables de entorno o un mecanismo de gestión de secretos apropiado.

Por ejemplo, en una sesión de Linux:

```bash
export VIG_TELEGRAM_TOKEN="TOKEN_CONFIGURADO_LOCALMENTE"
export VIG_TELEGRAM_CHAT_ID="CHAT_ID_CONFIGURADO_LOCALMENTE"
```

Este ejemplo es ilustrativo. Es preferible cargar los secretos desde un archivo privado con permisos restringidos o un gestor de secretos, evitando introducir valores reales en el historial de la terminal.

**No subir nunca:**

- Tokens de Telegram.
- Contraseñas de cámaras IP.
- Contraseñas Wi-Fi.
- Claves SSH privadas.
- Archivos `.env` con valores reales.
- Bases de datos que puedan contener información sensible.

## 9. Ejecución del prototipo

Los siguientes comandos corresponden a la instalación existente en la Raspberry de desarrollo.

### Procesamiento de vídeo y resumen por Telegram

```bash
~/vigilancia/.venv/bin/python \
  ~/vigilancia/prototipo/ejecutar_video_telegram_v11.py \
  --video ~/vigilancia/videos/matriculas_prueba.mp4
```

Este ejecutor procesa un vídeo local y genera un resumen informativo de la sesión.

Requiere que las credenciales de Telegram estén configuradas en el entorno.

### Consultar candidatos pendientes

```bash
~/vigilancia/.venv/bin/python \
  ~/vigilancia/prototipo/revision_ocr_v6.py \
  --pendientes
```

### Verificar manualmente un candidato

```bash
~/vigilancia/.venv/bin/python \
  ~/vigilancia/prototipo/revision_ocr_v6.py \
  --verificar ID --texto MATRICULA_VERIFICADA
```

Sustituir `ID` por el identificador real del candidato y `MATRICULA_VERIFICADA` por el texto confirmado durante la revisión.

### Rechazar un candidato

```bash
~/vigilancia/.venv/bin/python \
  ~/vigilancia/prototipo/revision_ocr_v6.py \
  --rechazar ID
```

### Generar un informe

```bash
~/vigilancia/.venv/bin/python \
  ~/vigilancia/prototipo/revision_ocr_v6.py \
  --informe
```

Estos comandos están sujetos a la estructura y configuración actuales del prototipo.

## 10. Persistencia de datos

VIGIA utiliza **SQLite** como almacenamiento local.

La base de datos de demostración permite conservar información asociada al procesamiento y revisión de lecturas.

La persistencia facilita:

- Consultar resultados históricos.
- Relacionar lecturas y candidatos.
- Registrar revisiones manuales.
- Dar soporte a la evaluación de reglas.
- Analizar el comportamiento del sistema durante las pruebas.

Las bases de datos reales quedan excluidas del repositorio.

## 11. Resultados de pruebas

El prototipo ha sido probado con un archivo MP4 local.

En una sesión de referencia se obtuvieron:

| Métrica | Resultado |
|---|---:|
| Fotogramas procesados | 93 |
| Intentos OCR | 24 |
| Errores registrados | 0 |
| Candidatos consolidados | 3 |
| Alertas críticas reales | No aplicable |

Los candidatos detectados permanecían pendientes de revisión humana.

Estos resultados corresponden a una prueba concreta y **no constituyen una medición general de precisión, rendimiento o fiabilidad del sistema**.

La integración de notificaciones informativas mediante Telegram también se ha probado satisfactoriamente.

## 12. Seguridad y privacidad

VIGIA se desarrolla como prototipo experimental.

Sus principios de diseño incluyen:

**Separación entre detección y verificación.** Una lectura OCR no se considera confirmada automáticamente.

**Alertas de demostración.** Las listas utilizadas para probar el motor de reglas son ficticias. Ninguna alerta implica una consulta a registros oficiales.

**Protección de credenciales.** Las claves y contraseñas se mantienen fuera del repositorio.

**Almacenamiento local.** Los datos del prototipo se gestionan mediante SQLite, sin que esto implique por sí mismo garantías de cifrado o anonimización.

**Acceso remoto privado.** El entorno de desarrollo utiliza Tailscale para facilitar el acceso remoto.

Antes de cualquier despliegue real, será necesario evaluar los requisitos de protección de datos, seguridad, conservación de imágenes, control de acceso y normativa aplicable.

## 13. Hoja de ruta

### Fase 1 — Prototipo con vídeo local

- [x] Preparación del entorno Raspberry Pi 5.
- [x] Integración de detección de objetos.
- [x] Seguimiento de objetos.
- [x] Procesamiento OCR.
- [x] Consolidación de candidatos.
- [x] Revisión manual.
- [x] Base de datos SQLite.
- [x] Envío de resúmenes informativos a Telegram.

### Fase 2 — Integración y fiabilidad

- [ ] Validación integral del flujo de alertas críticas simuladas.
- [ ] Unificación de módulos y reducción de duplicidades.
- [ ] Gestión centralizada de configuración.
- [ ] Inventario y fijación de dependencias.
- [ ] Pruebas automatizadas.
- [ ] Registro estructurado de errores y eventos.
- [ ] Mejoras de recuperación ante fallos.

### Fase 3 — Cámara IP

- [ ] Integración de TP-Link Tapo C200 mediante RTSP.
- [ ] Reconexión automática ante pérdida del flujo.
- [ ] Detección ligera de movimiento.
- [ ] Activación selectiva de inferencia.
- [ ] Regiones de interés configurables.
- [ ] Control de frecuencia de procesamiento.
- [ ] Reducción de consumo de CPU y memoria.

### Fase 4 — Evolución del sistema

- [ ] Panel local de supervisión.
- [ ] Gestión de múltiples cámaras.
- [ ] Configuración centralizada.
- [ ] Métricas de rendimiento.
- [ ] Gestión de eventos y notificaciones.
- [ ] Documentación de despliegue reproducible.
- [ ] Evaluación sistemática de precisión OCR.

Las fases futuras son objetivos de desarrollo, no funcionalidades actualmente disponibles.

## 14. Principios de desarrollo

El proyecto seguirá estas pautas:

1. Mantener los módulos funcionales mientras se desarrollan nuevas versiones.
2. Evitar cambios destructivos sin pruebas previas.
3. Separar configuración, credenciales y código fuente.
4. Registrar errores de forma trazable.
5. Priorizar el rendimiento en hardware limitado.
6. Verificar manualmente los candidatos antes de emitir alertas críticas simuladas.
7. Documentar las decisiones técnicas y los cambios importantes.
8. Diferenciar claramente los resultados comprobados de las funcionalidades experimentales.

## 15. Limitaciones actuales

El sistema todavía presenta limitaciones propias de un prototipo:

- El reconocimiento OCR puede producir lecturas incorrectas.
- Los resultados dependen de la resolución, iluminación, movimiento y posición de la cámara.
- No existe una garantía de identificación correcta de matrículas.
- La integración RTSP está pendiente.
- No se ha validado todavía el funcionamiento continuo durante largos periodos.
- El sistema no está preparado para utilizarse como herramienta autónoma de vigilancia operativa o identificación oficial.

## 16. Contribuciones y desarrollo

El repositorio está destinado a centralizar el desarrollo técnico de VIGIA.

Las nuevas contribuciones deberían incluir, cuando corresponda:

- Descripción del cambio.
- Archivos modificados.
- Instrucciones de ejecución.
- Pruebas realizadas.
- Limitaciones conocidas.
- Confirmación de que no se han añadido credenciales ni datos sensibles.

## 17. Estado y alcance

**VIGIA es un proyecto experimental de investigación y desarrollo en visión artificial.**

No está diseñado para identificar personas, consultar bases de datos policiales ni sustituir procedimientos de verificación humana.

El uso de cámaras y el tratamiento de matrículas deberán ajustarse a la legislación aplicable en cualquier entorno de despliegue real.

---

**VIGIA — Visión inteligente, análisis y vigilancia asistida por IA.**

*Desarrollado sobre Raspberry Pi 5.*
