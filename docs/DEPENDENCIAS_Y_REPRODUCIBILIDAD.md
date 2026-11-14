# Dependencias — procedimiento seguro

No se genera un `requirements.txt` con versiones supuestas: el código original y los entornos Python no están disponibles en este paquete. **Ejecuta el script `inventariar_entornos.sh` en la Raspberry** para obtener inventarios reales, y revisa los resultados antes de subirlos.

## Inventario en Raspberry
```bash
cd ~/vigilancia
bash inventariar_entornos.sh
```
Si el script está en el directorio del paquete descargado, usa su ruta real o cópialo a la Raspberry. Genera archivos en `~/entrega-work/dependencias/`, no altera el entorno.

## Construcción posterior de requirements
1. Comparar los imports de `prototipo/*.py` con `pip freeze` de `.venv` y `.venv-ocr`.
2. Separar dependencias directas de transitivas; identificar paquetes locales y wheels NCNN específicos ARM64.
3. Registrar versiones Python/OS y cualquier instalación manual.
4. Crear `requirements.in` con dependencias directas verificadas y `requirements-lock.txt`/archivo de restricciones para el entorno concreto.
5. Verificar instalación en un entorno nuevo y ejecutar smoke tests antes de sustituir el entorno que funciona.
6. No añadir paquetes por intuición: por ejemplo, los nombres de imports y de distribuciones pip pueden diferir.

## Atención a secretos
Un inventario `pip freeze` suele ser inocuo, pero puede incluir URLs de repositorios privados con credenciales embebidas o rutas locales. **Revisar/redactar antes de subirlo.** El script genera un reporte local para revisión, no lo publica.
