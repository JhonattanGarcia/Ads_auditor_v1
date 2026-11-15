# Estructura y responsabilidades

Estado: esqueleto inicial. Solo estan operativos la ayuda CLI, la version y los valores predeterminados. Los modulos con una descripcion reservan responsabilidades futuras; no implementan aun las funciones del MVP.

| Ubicacion | Responsabilidad |
| --- | --- |
| cli.py, __main__.py | Entrada de la aplicacion |
| config/ | Ajustes, carga y validacion de perfiles JSON |
| domain/ | Entidades, estados y reglas independientes de UI y fuente |
| search/ | Analisis de URL, rangos temporales y generacion de consultas |
| collectors/ | Contrato de fuentes y adaptador Meta reemplazable |
| ingestion/ | Normalizacion, deduplicacion y coordinacion de corridas |
| storage/ | SQLite, migraciones y persistencia |
| lists/ | Blanca/negra por anunciante, marron por anuncio y conflictos |
| review/ | Cola, clasificaciones, correcciones y reporte manual |
| evidence/ | Referencias, archivos permitidos y hashes |
| history/ | Consultas de historicos, URLs y metricas |
| exports/ | Expedientes e intercambio CSV/JSON |
| backups/ | Respaldo consistente y restauracion verificada |
| ui/ | Inicio, auditoria y vistas auxiliares; framework pendiente |
| tests/ | Pruebas unitarias, integracion y escenarios completos |
| profiles/ | Ejemplo versionado y perfiles privados locales |
| data/ | Estado local generado, excluido de Git |

Dependencias previstas: UI y CLI llaman servicios; los servicios usan dominio y contratos de persistencia/recoleccion. El dominio no depende de UI, Meta ni SQLite. El adaptador no decide clasificaciones humanas. No se automatizan reportes a Meta.

Consultar ROADMAP.md para el orden de implementacion y URL_SEARCH_SPEC.md para el contrato de busquedas. Las migraciones, contratos completos, framework UI y dependencias adicionales se definiran en sus fases.


## Decision de interfaz inicial (15 noviembre 2026)

Se implementa escritorio Tkinter por disponibilidad local y ausencia de servidor obligatorio. Primera comprobacion: construccion de Inicio/Auditoria, carga de manifiesto y seleccion de anuncio ficticio con detalle sin abrir enlaces. La decision se valida como base tecnica, no como aceptacion ergonomica final del analista. ui/app.py coordina widgets; ingestion/collector.py comparte recoleccion con la CLI. Un hilo ejecuta consultas con conexion SQLite propia y publica eventos a la ventana mediante queue.Queue/after.

Pendientes: separar componentes visuales cuando aumenten, multimedia, historicos completos, editor de perfiles, correcciones/reportes visuales y accesibilidad exhaustiva.
