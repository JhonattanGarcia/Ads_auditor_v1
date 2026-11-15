# Contrato de recolectores

Collector define nombre/version, capacidades, estadisticas, ciclo de vida mediante contexto y search(query, country, max_results, cancel_event). search emite CollectedAd independientes de la biblioteca externa: ID de anuncio como cadena, fecha de inicio con zona cuando exista, anunciante opcional y payload conservado.

El consumidor valida identidad/fechas y decide que conservar. El adaptador nunca clasifica fraude ni cambia listas. Un fallo produce CollectorError sin invalidar resultados previamente emitidos. La cancelacion cooperativa produce CollectorCancelled, una excepcion distinta que el ejecutor registra como cancelled.

La cancelacion se comprueba antes de empezar y entre resultados: no interrumpe una peticion HTTP en curso. Los timeouts y reintentos pertenecen al proveedor. KeyboardInterrupt sigue permitiendo guardar resultados parciales.

MetaCollector conserva paginacion del proveedor, expone sus estadisticas y traduce sus modelos/errores. No soporta fechas en servidor ni descarga de medios en este contrato. El ejecutor filtra fechas localmente y siempre declara cobertura parcial. Su URL efectiva representa la intencion de busqueda; server_filters describe lo que realmente se envia.

FixtureCollector reproduce datos inventados de tests/fixtures/collector_ads.json sin red. Permite simular fallo tras N resultados y cancelacion. No demuestra cobertura ni equivalencia con Meta.

Para incorporar otro proveedor, implementar el protocolo y suministrar su fabrica a collect. La ejecucion actual sigue especializada en Meta para metadatos y opciones de busqueda; generalizar esos campos corresponde a la integracion de ingesta. El contrato se limita por ahora a las opciones de la busqueda validada.
