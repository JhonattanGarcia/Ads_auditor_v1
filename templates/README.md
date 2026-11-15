# Formatos JSON de salida

Estas plantillas vacias describen la salida prevista. No son resultados recolectados y no se cargan como datos reales. La escritura automatica aun no esta implementada.

Cada corrida escribira `data/results/<run_id>/results.json` y `run_summary.json`, fuera de Git. SQLite sera la fuente de verdad; estos archivos permiten inspeccion e intercambio.

## results.json

- run_id, source y source_version: identificacion de corrida y adaptador.
- coverage: not_evaluated, complete, partial o unknown; complete solo cuando pueda justificarse el alcance consultado, nunca cobertura total de Meta.
- queries: query_id, client_id, country, criterion, original_url, effective_url, date_range, temporal_filter_status, status y warnings.
- ads: source, ad_id y advertiser_id como cadenas; title, body, library_url, media y urls con valores ausentes explicitos. Los medios son referencias, no contenido ejecutable. Cada URL distingue original, normalizada y tipo.
- observations: run_id, query_id, source, ad_id y observed_at con zona horaria. Un anuncio puede tener varias procedencias de consulta sin duplicar su entidad.
- invalid_records: query_id, motivo y datos permitidos para registros sin identidad valida; no pueden generar decisiones permanentes.

## run_summary.json

Estados previstos: not_started, running, completed, partial, failed y cancelled. El resumen registra inicio/fin, dia de referencia local, perfiles, conteos conocidos, advertencias y errores accionables. Los ceros iniciales son solo valores de plantilla. En ejecucion, conteos no disponibles deben ser null y no inventarse como cero. Las categorias no son necesariamente disjuntas y no deben sumarse como si lo fueran.

Las decisiones humanas, listas e historial no deben reconstruirse solamente desde estos archivos: se conservaran transaccionalmente en SQLite. Las reglas completas de normalizacion y validacion se implementaran con la ingesta.
