# Datos locales

Contenido generado y excluido de Git:

- database/: SQLite y archivos auxiliares.
- evidence/: medios y evidencias permitidas.
- exports/: expedientes y listas exportadas.
- backups/: respaldos de base, perfiles y evidencia.
- logs/: registros de ejecucion sin secretos.

Las carpetas se incluyen vacias como referencia. La aplicacion aun no escribe datos en ellas. El directorio de datos sera configurable.

- results/: resultados y resumen por ejecucion en `<run_id>/results.json` y `<run_id>/run_summary.json`. Los formatos vacios versionados estan en `templates/`.
