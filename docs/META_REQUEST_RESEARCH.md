# Investigación: solicitudes a Meta y organización por fecha

Fecha de consulta: 17 de noviembre de 2026.
Alcance: documentación oficial y fuentes técnicas primarias. Esta investigación no modifica el recolector ni confirma cobertura completa.

## Hallazgos verificables

### API oficial

Meta documenta `GET /<VERSION>/ads_archive`, con `search_terms`, `ad_reached_countries`, `ad_active_status`, `ad_delivery_date_min` y `ad_delivery_date_max`. Los límites temporales son inclusivos y usan YYYY-MM-DD. La descripción se refiere a entrega del anuncio, no a fecha de observación de nuestra herramienta. No se deben trasladar automáticamente estos parámetros a GraphQL interno.

La cobertura oficial contempla publicidad política/social y anuncios entregados en UE/Reino Unido según el alcance indicado por Meta. No equivale a cualquier anuncio comercial mostrado exclusivamente en SV o CO. El alta de acceso requiere autorización, cuenta de desarrollador y token. Por ello no es un sustituto universal de la fuente actual.

Fuentes oficiales:

- [Referencia Ads Archive](https://developers.facebook.com/docs/graph-api/reference/ads_archive/).
- [Alcance y acceso de Ad Library API](https://br-fr.facebook.com/ads/library/api/).
- [Ejemplos mantenidos bajo facebookresearch](https://github.com/facebookresearch/Ad-Library-API-Script-Repository). Su README no proporciona una guía completa actualizada; usarlo como ejemplo, no como garantía de vigencia.

### Ordenación y filtros del recolector actual

El código público de MetaAdsCollector admite impresiones o relevancia; no una opción cronológica validada. Su cliente construye la consulta interna y originalmente deja `startDate` sin valor. El módulo de filtros aplica fechas en el cliente. Las opciones de una API no prueban que otra interfaz acepte los mismos valores.

Fuentes primarias:

- [Modos de orden admitidos](https://github.com/promisingcoder/MetaAdsCollector/blob/main/meta_ads_collector/constants.py).
- [Construcción de la solicitud](https://github.com/promisingcoder/MetaAdsCollector/blob/main/meta_ads_collector/client.py).
- [Filtros locales](https://github.com/promisingcoder/MetaAdsCollector/blob/main/meta_ads_collector/filters.py).

### Reporte independiente del filtro ignorado

Un desarrollador describe mediciones donde fechas y formatos multimedia solicitados al endpoint interno no se aplicaron como esperaba. Recomienda filtrar lo recibido y mostrar el volumen inspeccionado frente al aceptado. Es evidencia experimental de su entorno, no especificación contractual de Meta ni prueba de que ocurra siempre.

Fuente primaria: [Matvey: Scraping Meta’s Ad Library Without a Browser](https://dev.to/matveyg/scraping-metas-ad-library-without-a-browser-the-200-ok-that-means-blocked-18og), sección sobre filtros aceptados e ignorados. Las afirmaciones generales del artículo sobre cobertura oficial no se usan: prevalece la documentación de Meta.

### Primera consulta y paginación pueden diferir

Un ejemplo público distingue `AdLibraryMobileFocusedStateProviderRefetchQuery` para la primera página y `AdLibrarySearchPaginationQuery` para páginas posteriores; incluye fechas min/max y cursor. Fue publicado en 2025. Sirve como pista para comparar solicitudes de una sesión actual, no para copiar sus identificadores antiguos y esperar compatibilidad.

Fuente primaria: [Código del recolector publicado por hashcott](https://gist.github.com/hashcott/c0d1d983ba2f173a7899b51073c794c6).

Hipótesis pendiente: la diferencia entre consulta inicial, identificador del documento, contexto de sesión y paginación podría explicar parte de la discrepancia con la interfaz manual. No se ha demostrado en nuestro caso.

### Reglas de paginación

La guía general Graph API recomienda continuar mediante los enlaces/cursor devueltos y no deducir el final de una página corta. Advierte que puede haber páginas vacías con enlace siguiente y que los cursores no son una referencia permanente. Esa guía no constituye la especificación del endpoint web: en este último se deben registrar y respetar sus propios indicadores de continuación.

Fuentes: [Paginación oficial Graph API](https://developers.facebook.com/docs/graph-api/results/) y [parser de respuesta del recolector](https://github.com/promisingcoder/MetaAdsCollector/blob/main/meta_ads_collector/client.py).

## Contraste con nuestro experimento

Datos locales, sin nueva consulta en esta investigación:

- chivo / SV, intervalo 16–17 noviembre.
- 100 anuncios recibidos en 10 páginas.
- 19 coincidencias por fecha local de inicio; 81 fuera de intervalo.
- El primer anuncio antiguo no impidió encontrar coincidencias en páginas posteriores.

Artefacto: `data/results/date_guard_experiment_20261117/results.json`, excluido de Git. El experimento confirma una mezcla de fechas en esta muestra y que el freno anterior era prematuro; no prueba agotamiento de resultados.

## Organización recomendada de resultados

Propuesta de diseño, no una capacidad nueva ya implementada:

1. Conservar cada anuncio recibido, procedencia, fecha de inicio de fuente, fecha local y fecha de observación como campos distintos.
2. Filtrar el conjunto recibido por el intervalo acordado. Mostrar sin ambigüedad si significa anuncios iniciados en el rango o anuncios activos/entregados en él: son preguntas diferentes.
3. Ordenar las coincidencias localmente por fecha de inicio descendente, con ID como desempate estable. Si se mantienen prioridades de listas, ofrecer fecha dentro de prioridad o un orden global por fecha explícito.
4. Conservar `received_ads` para diagnóstico y mantener separadas las coincidencias destinadas a auditoría.
5. Paginar hasta agotamiento confirmado o presupuesto de páginas, anuncios y tiempo. No detenerse al primer anuncio viejo sin garantía cronológica.
6. Mostrar recibidos, descartados, aceptados, páginas y razón de finalización; un tope no significa búsqueda exhaustiva.
7. Para vigilancia repetida, deduplicar por ID/fuente y señalar nuevas observaciones. Esto reduce trabajo humano, pero no garantiza que Meta entregue solo anuncios nuevos.

Ordenar localmente organiza lo obtenido; no reduce retroactivamente las peticiones ni demuestra que no existan anuncios omitidos.

## Siguiente experimento recomendado

Comparar en una sesión normal de navegador la consulta manual de chivo/SV con el adaptador: misma palabra, país, estado y rango. Observar la petición inicial y la primera continuación, registrar nombres de operación y variables no sensibles y contrastar IDs/fechas. No guardar cookies ni tokens en reportes o Git. No eludir retos, restricciones ni límites de acceso.

Con ese contraste, decidir si se puede corregir el adaptador interno o si conviene otra fuente autorizada. Probar por separado impresiones y relevancia, midiendo proporción de coincidencias recientes; no presentar relevancia como orden temporal. Mantener recolección diagnóstica acotada mientras no se valide el filtro del servidor.

## Límites de la investigación

La URL principal de API devolvió 403 en una lectura; la referencia oficial y la variante localizada sí fueron legibles. La página de campos archived-ad pidió inicio de sesión. No se verificó una sesión de navegador del usuario, no se ejecutaron nuevas peticiones de anuncios y no se encontró una opción cronológica documentada y compatible con nuestro recolector actual. Los ejemplos de terceros y los identificadores internos pueden cambiar.
