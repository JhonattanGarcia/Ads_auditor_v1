# Contrato de URLs de búsqueda de Meta

Referencia funcional: URL aportada por el usuario el 14 de noviembre de 2026. Especificación de implementación para RF-003 y RF-004; el comportamiento efectivo de los filtros de Meta debe validarse con el conector en la fase 0.

## Descomposición del ejemplo

Base: `https://www.facebook.com/ads/library/`.

| Parámetro | Valor recibido | Interpretación prevista |
| --- | --- | --- |
| active_status | active | Solicitar anuncios activos |
| ad_type | all | Todos los tipos de anuncio admitidos por la búsqueda |
| country | CO | País de consulta: Colombia |
| is_targeted_country | false | Opción de segmentación territorial de la fuente; conservar sin asumir que equivale a país de origen del anunciante |
| media_type | all | Sin restricción de formato multimedia |
| q | pichincha | Texto del criterio de búsqueda, no ID ni nombre necesariamente autorizado |
| search_type | keyword_unordered | Modalidad de palabras clave de la fuente; conservar y validar su comportamiento |
| sort_data[direction] | desc | Dirección descendente |
| sort_data[mode] | total_impressions | Modo de ordenación solicitado; no implica que se obtengan cifras de impresiones |
| start_date[min] | 2026-11-13 | Límite inferior solicitado para fecha de inicio del anuncio |
| start_date[max] | vacío | Sin límite superior explícito; el ejemplo no restringe por sí mismo a un único día |

Los corchetes son parte del nombre del parámetro. Al serializar se codifican como `%5B` y `%5D`. Un parámetro sin `=` debe leerse como valor vacío, no perderse durante el análisis. Los escapes de Markdown (`\&`, `\[`, `\]` y `\:`) se limpian únicamente al importar un enlace copiado como texto; no se altera el contenido de una URL ya válida.

## Perfil JSON propuesto

Ver `profiles/example.json`. Extiende el perfil del documento con `timezone` y `search`. Es una propuesta de contrato para el futuro validador; todavía no existe un motor que la ejecute.

Prioridad de valores: configuración explícita del JSON > valores de la URL plantilla > valores predeterminados. Las fechas son la excepción deliberada: se recalculan según el modo temporal y no se reutilizan fechas antiguas de la plantilla. País y criterio provienen siempre del perfil y del criterio habilitado que se esté ejecutando.

- `country`: normalizar a mayúsculas para URL; validar código de país admitido.
- `criteria`: producir una URL por criterio habilitado y por perfil habilitado.
- `search.template_url`: base y opciones reutilizables; nunca debe fijar para siempre marca, país o fecha.
- `search.parameters`: opciones explícitas del perfil; no admitir aquí q, country ni start_date[min/max], que tienen campos propios.
- `timezone`: por defecto `America/Bogota`. Resolver el día local una sola vez al iniciar la ejecución para evitar cambiar de fecha entre criterios al cruzar medianoche.

## Política temporal

1. Sin configuración temporal: modo `today`, mínimo y máximo iguales al día local de ejecución. El valor predeterminado de `days_to_review` pasa a ser 1.
2. Si el JSON especifica `days_to_review = N` y omite `date_range.mode`, usar ventana inclusiva de N días terminada hoy: mínimo = hoy menos N-1 días; máximo = hoy. Exigir entero positivo.
3. `date_range.mode = today`: equivale a un día. Si se especifica además days_to_review distinto de 1, rechazar por contradicción en vez de ignorarlo.
4. `date_range.mode = rolling_days`: usar days_to_review obligatorio y positivo con la fórmula anterior.
5. `date_range.mode = fixed`: exigir min y max ISO `YYYY-MM-DD`, min <= max y sin fechas futuras para este flujo de vigilancia. No combinar con days_to_review. No sustituir fechas fijas por hoy.
6. Rechazar modos, fechas, zonas horarias o configuraciones contradictorias antes de consultar.

Con fecha local de ejecución 2026-11-14 y modo predeterminado, la URL recibida cambia `start_date[min]` de 2026-11-13 a 2026-11-14 y completa `start_date[max]=2026-11-14`. Con days_to_review=2, produce min=2026-11-13 y max=2026-11-14. Las fechas de ejemplo no deben codificarse como constantes en el programa.

**Distinción funcional:** estos parámetros solicitan un intervalo de fecha de inicio de anuncios. No equivalen necesariamente a todos los anuncios que estuvieron activos u observados ese día. Mantener por separado la fecha de observación local. Si Meta ignora el máximo, aplica otra semántica o no admite el filtro, mostrar la limitación y marcar el filtro no verificado/no soportado; nunca ampliar silenciosamente el intervalo ni presentar la consulta como cobertura garantizada. Un filtro local solo es válido si existe una fecha de inicio fiable, y debe declararse como tal.

## Algoritmo previsto

1. Importar la URL y conservar su versión original. Aceptar únicamente HTTPS, host exacto www.facebook.com o facebook.com, sin credenciales ni puerto alternativo, y ruta /ads/library/.
2. Usar un analizador estándar de URLs y query strings con preservación de valores vacíos; no concatenar parámetros manualmente. Detectar parámetros duplicados y rechazar ambigüedades.
3. Descomponer parámetros conocidos. Conservar desconocidos para diagnóstico, sin reenviarlos automáticamente hasta que el adaptador los reconozca.
4. Validar perfil, opciones y criterio; resolver país, consulta y rango temporal siguiendo las reglas anteriores.
5. Reemplazar los parámetros gestionados; mantener opciones conocidas de plantilla que no estén sobrescritas. Codificar correctamente tildes, espacios, ampersands y corchetes.
6. Registrar URL original, URL efectiva, fecha/zona de referencia y diferencias con motivo: por ejemplo country: CO → EC, q: pichincha → otro criterio, fecha mínima actualizada o máxima completada.
7. Mostrar URL efectiva y rango antes de ejecutar. Guardar el resultado en la consulta de la corrida junto con la capacidad temporal declarada por el adaptador.

## Criterios de aceptación a implementar

- Plantilla del ejemplo + hoy 2026-11-14: min=max=2026-11-14; no queda el límite de ayer ni un máximo vacío.
- Perfil country=ec y criterio distinto: reemplaza ambos valores, sin duplicar parámetros y sin modificar opciones ajenas.
- Ventana de 7 días con hoy 2026-11-14: 2026-11-08 a 2026-11-14 inclusivos.
- Rango fijo válido: conserva las fechas del JSON aunque la plantilla tenga otras.
- Criterio con tildes, espacios o &: al volver a analizar la URL se recupera exactamente el criterio original.
- Máximo sin valor en la URL: se conserva durante el análisis y se completa al adaptar.
- Zonas horarias y cambio de medianoche: todos los criterios de la misma corrida usan el mismo día de referencia local.
- Parámetros duplicados, host ajeno, fechas inválidas o configuración contradictoria: error accionable antes de ejecutar.
- Filtro no soportado por la fuente: advertencia visible y capacidad registrada, sin afirmar que se revisó solo ese día.
