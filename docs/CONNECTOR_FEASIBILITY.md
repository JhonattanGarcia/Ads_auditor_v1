# Validacion inicial del conector

Fecha: 15 de noviembre de 2026. Fuente tecnica provisional: meta-ads-collector 1.7.2. Consulta: pichincha, CO, anuncios activos, palabras desordenadas, orden por impresiones.

## Evidencia observada

Las corridas locales de diagnostic_comparison y diagnostic_100 recuperaron 30 y 68 anuncios respectivamente. Las rutas estan excluidas de Git; no se incluyen datos reales como fixtures. Se observaron IDs, fechas de inicio y payloads de anuncios; no se garantiza que todos los registros contengan texto, anunciante, medios o URLs.

La consulta ampliada encontro 1150385804209505 con inicio 2026-11-14T08:00:00+00:00 y 991467333511027 con inicio 2026-06-26T07:00:00+00:00. Ambos se excluyeron correctamente del filtro local del 15 de noviembre. El primer caso coincide con el texto manual aportado por el usuario, fechado el 14. La consulta directa de detalles del segundo ID fallo; esto no demuestra inexistencia del anuncio.

## Limitaciones confirmadas

- La biblioteca envia startDate=None: no aplica el intervalo en servidor. El filtro local sobre una consulta limitada no reproduce la busqueda manual filtrada antes de paginar.
- Los primeros 30 resultados por impresiones pueden omitir anuncios recientes; elevar el limite no garantiza cobertura.
- La implementacion del proveedor fija isTargetedCountry=False, coincidente con la plantilla.
- URL efectiva significa URL solicitada, no navegacion literal. Los filtros efectivos de servidor se registran aparte.
- La fecha local depende de America/Bogota y se fija al preparar la corrida.
- No se descargaron medios ni se validaron permisos de almacenamiento. Tampoco se establecio autorizacion de automatizacion por parte de Meta.

## Decision provisional

Conservar el adaptador para desarrollo y pruebas de alcance acotado, sin declarar resuelta la viabilidad integral ni cobertura exhaustiva. Desacoplarlo mediante collectors/base.py y usar fixtures ficticios para pruebas reproducibles.

Pendiente: revision de condiciones de consulta/almacenamiento, validacion del filtro temporal en servidor, continuidad y equivalencia de paginacion, seleccion final de fuente y ergonomia de interfaz. Estas tareas mantienen abierta la fase 0.
