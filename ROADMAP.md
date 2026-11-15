# Roadmap — Brand Threat Monitor

Fecha: 14 de noviembre de 2026.
Fuente: `documentación/Requisitos_Funcionales_Brand_Threat_Monitor.pdf`, versión 1.0, 18 páginas.
Estado: fase 0 parcialmente validada; fase 1 en curso con esquema SQLite, migraciones e importacion idempotente de resultados. Ninguna fase completa aun.

## Objetivo y alcance

Construir una aplicación local con Python, SQLite e interfaz local para convertir búsquedas de anuncios por marca y país en una cola priorizada y auditable. El analista decide la clasificación y realiza los reportes a Meta manualmente.

El MVP completo incluye configuración JSON, recolección desacoplada, persistencia, listas, auditoría, evidencia disponible, históricos, exportación básica y respaldo/restauración. La disponibilidad de campos y cobertura depende de la fuente validada.

Quedan fuera del MVP: denuncias automáticas, bloqueo de páginas, navegación automática a destinos sospechosos, atribución legal, IA, reconocimiento avanzado de logos y operación distribuida. No se promete cobertura total ni recuperación retrospectiva que la fuente no permita.

## Reglas que condicionan toda la implementación

- Blanca y negra cruzan por `advertiser_id`; marrón cruza exclusivamente por `ad_id`. Todas las identidades se distinguen por fuente.
- Resolver conflictos blanca/negra explícitamente antes de clasificar. Sin conflicto, aplicar negra → blanca → marrón → desconocido.
- Un anunciante negro da prioridad a cada anuncio nuevo; no confirma automáticamente fraude ni un reporte individual.
- Persistir observaciones aunque un anuncio quede fuera de la cola. Separar primera/última observación de las fechas de publicación que informe la fuente.
- Guardar clasificación, efecto en listas y evento de auditoría en una misma transacción. Corregir mediante eventos con justificación, sin borrar historia.
- Mantener separados clasificación, prioridad, estado de revisión y estado del reporte externo.

## Secuencia de entrega

Las fases se ejecutan en orden. Las pruebas, seguridad y trazabilidad se incorporan desde cada fase; la última consolida la validación integral. No se fijan fechas hasta resolver viabilidad, interfaz y capacidad de trabajo.

### Fase 0 — Viabilidad y decisiones técnicas

- [ ] Probar una consulta real de un país y criterio representativos; documentar acceso permitido, campos, IDs, URLs, paginación, errores y cobertura.
- [ ] Evaluar condiciones de consulta y almacenamiento de medios antes de seleccionar un conector; no asumir acceso oficial a anuncios comerciales de Colombia.
- [x] Definir contrato reemplazable del adaptador: consulta, normalización, versión, capacidades, fallos, cancelación y resultados parciales.
- [x] Preparar datos de prueba reproducibles para desarrollar sin depender de Meta. Estos datos no sustituyen la validación real del conector.
- [ ] Elegir interfaz local tras comprobar las dos pantallas principales; registrar la decisión sin imponer aún un framework.
- [ ] Acordar alcance de listas, evidencia mínima de Ataque e identificación del analista.

**Salida:** informe de viabilidad con una búsqueda real reproducible, limitaciones explícitas y decisión de fuente. Si no existe una fuente viable, continuar con datos de prueba y dejar la integración real bloqueada, sin presentarla como operativa.

**Trazabilidad:** RF-003, RF-004, RF-009, RF-014; RNF-01, RNF-03, RNF-11.

### Fase 1 — Base local, perfiles e integridad

- [ ] Separar configuración, recolección, normalización, almacenamiento, listas, auditoría e interfaz.
- [x] Crear esquema SQLite y migraciones para clientes, criterios, ejecuciones/consultas, anunciantes, anuncios, observaciones, URLs, listas, casos, reportes, evidencia y audit_log.
- [x] Definir claves únicas por fuente, relaciones e índices; evitar duplicados de anuncio y de vínculo anuncio/ejecución. Preservar la procedencia por consulta cuando varias consultas encuentren el mismo anuncio.
- [ ] Validar perfiles JSON versionados, país, cliente, criterios y activación; permitir seleccionar perfiles independientes y editar la tabla de configuración.
- [ ] Implementar análisis y adaptación de URLs conforme a `URL_SEARCH_SPEC.md`: JSON prioritario, día actual de Colombia por defecto, ventanas inclusivas, rangos fijos y registro de diferencias. Usar `profiles/example.json` como ejemplo de contrato propuesto.
- [ ] Configurar y validar rutas de perfiles, base, medios, resultados, exportaciones, respaldos y logs.
- [ ] Implementar transacciones, eventos de auditoría, identificación de actor y respaldo inicial. Activar WAL cuando corresponda.

**Salida:** perfiles válidos habilitan ejecución; perfiles inválidos muestran campo y causa. Base inicial migrable y cambios auditables.

**Trazabilidad:** RF-001–007, RF-038, RF-041; RNF-02–05. Pruebas CA-01 y CA-02.

### Fase 2 — Recolección, ingesta y observaciones

- [ ] Integrar el adaptador validado con inicio, detención controlada y progreso por criterio.
- [ ] Registrar RUN_ID, consultas y URLs, inicio/fin, versión de fuente, conteos, advertencias y estado.
- [ ] Conservar datos normalizados y datos brutos cuando esté permitido; deduplicar por fuente/ad_id y vincular observaciones sin duplicar anuncios.
- [ ] Preservar datos válidos ante fallo, cancelación o paginación incompleta; permitir reintento idempotente.
- [ ] Aislar ingestas sin ID válido y marcar información incompleta; impedir decisiones permanentes sobre identidades no verificadas.
- [ ] Registrar URLs originales/normalizadas y su tipo. Capturar referencias de medios disponibles; las descargas se completan en fase 4.
- [ ] Mostrar errores accionables y métricas reales por ejecución, sin equiparar observación a monitoreo en vivo.

**Salida:** una ejecución repetida no duplica anuncios; un fallo parcial conserva lo obtenido y declara cobertura incompleta.

**Trazabilidad:** RF-008–016, RF-040, RF-042; RNF-04, RNF-05, RNF-09. Pruebas CA-03, CA-11 y E2E-C.

### Fase 3 — Listas, cola y auditoría humana

- [ ] Implementar blanca/negra por anunciante y marrón por anuncio, con scope, motivo, autor, fecha y procedencia.
- [ ] Resolver conflictos blanca/negra sin decisiones automáticas ni eliminación silenciosa.
- [ ] Aplicar precedencia y conservar observaciones de blancos/marrones; ofrecer revisión extraordinaria.
- [ ] Construir cola determinista con motivo visible, filtros, ordenación y búsqueda exacta de IDs. La temperatura representa atención, sin expresar probabilidad de fraude.
- [ ] Implementar Inicio/Configuración y Auditoría; mostrar IDs, texto, título, medios y URLs disponibles, con marcadores de ausencias e historial del anunciante.
- [ ] Mantener posición, filtros y avance al navegar entre casos.
- [ ] Spam: confirmar el anuncio y crear marrón. Ataque: confirmar alcance del anunciante y exigir motivo, evidencia y antecedente. Pendiente: conservar caso sin modificar listas.
- [ ] Permitir correcciones justificadas y actualizar estado efectivo sin borrar eventos.
- [ ] Abrir deliberadamente el anuncio original de Biblioteca; evitar aperturas automáticas de destinos sospechosos.

**Salida:** flujo de revisión operable, persistente y auditable; un anuncio marrón de anunciante negro sigue priorizado y Spam no excluye otros anuncios del anunciante.

**Trazabilidad:** RF-017–031, RF-041, RF-043, RF-044; RN-01–05; RNF-06, RNF-07, RNF-10. Pruebas CA-04–10, CA-12 y E2E-A.

### Fase 4 — Evidencia, reportes, históricos y portabilidad

- [ ] Guardar medios permitidos con hashes, tipos/tamaños limitados y rutas saneadas; tolerar fallos de descarga con referencia original y marcador de ausencia.
- [ ] Registrar reportes manuales por caso/anuncio con actor, fecha, plataforma, referencia disponible, notas y estado externo conocido. No inferir aceptación ni retirada.
- [ ] Entregar Históricos, Listado URLs y detalle del anunciante con relaciones, cronología y búsqueda.
- [ ] Importar/exportar listas CSV/JSON con validación, duplicados, procedencia, respaldo previo y gestión explícita de conflictos.
- [ ] Exportar expediente por anuncio en JSON/CSV con datos realmente obtenidos; proteger CSV contra fórmulas. PDF queda opcional.
- [ ] Implementar respaldo consistente y restauración verificada de SQLite, perfiles y evidencia, con comprobación de integridad.
- [ ] Completar métricas de encontrados, nuevos, negros, blancos, marrones, pendientes, incompletos y reportados.

**Salida:** expediente reconstruible, reporte manual diferenciado de resolución externa y restauración comprobada en una ubicación de prueba.

**Trazabilidad:** RF-015, RF-025, RF-032–040; RNF-02, RNF-06–09. Pruebas CA-13–15 y E2E-B.

### Fase 5 — Validación integral y entrega del MVP

- [ ] Ejecutar CA-01–15 y E2E-A/B/C con datos reproducibles y una prueba de integración real de alcance conocido.
- [ ] Verificar atomicidad ante error, reversión, conflicto entre listas, reintentos, reinicio de la aplicación y persistencia del avance.
- [ ] Verificar escape de contenido, navegación deliberada, ausencia de secretos en logs, límites de archivos y retención configurable.
- [ ] Revisar teclado, contraste, etiquetas y prioridades comprensibles sin depender solo del color.
- [ ] Añadir prueba de humo que detecte rupturas del adaptador y documentar diagnóstico, cobertura y límites.
- [ ] Documentar instalación, configuración, revisión, reporte manual, respaldo y restauración; realizar piloto con un perfil y aceptar los resultados con el analista.

**Salida:** todos los criterios del MVP aprobados, limitaciones documentadas y respaldo restaurado correctamente. Los controles RNF-01–12 aplicables quedan verificados; no se requieren servicios externos de reputación para el flujo básico.

**Trazabilidad:** RF-001–044; CA-01–15; E2E-A/B/C; RNF-01–12.

### Evolución posterior — Opcional

- [ ] Programación configurable con límites y visibilidad de cobertura.
- [ ] Correlaciones entre anuncios, anunciantes y URLs con explicación de señales.
- [ ] Reputación externa bajo demanda, previa validación de licencias, cuotas y sanitización de URLs; no enviar tokens ni datos sensibles a servicios públicos.
- [ ] Exportación PDF y mejoras de priorización basadas en resultados del piloto.

Estas funciones no condicionan la aceptación del MVP. IA, análisis activo de destinos y operación distribuida requieren definición de alcance adicional.

## Decisiones pendientes y propuestas

| Decisión | Propuesta del documento | Resolver antes de |
| --- | --- | --- |
| Fuente/conector de Meta | Elegir después de medir cobertura y validar condiciones; adaptador intercambiable | Fase 2 |
| Interfaz local | Evaluar ergonomía de interfaz web local frente a escritorio nativo | Fase 1 |
| Alcance de blacklist | Global, por fuente/advertiser_id, con antecedente vinculado | Fase 3 |
| Alcance de whitelist | Por cliente o contexto | Fase 3 |
| Alcance de brownlist | Por fuente/ad_id, con scope de perfil configurable | Fase 3 |
| Evidencia mínima para Ataque | Acordar categorías, protocolo y evidencia verificable | Fase 3 |
| Ventana y frecuencia | Manual en MVP; comunicar límites retrospectivos de la fuente | Fase 2 |
| Retención y volumen | Fijar límites de medios, espacio y conservación según piloto | Fase 4 |

Las propuestas no representan decisiones aprobadas. No se selecciona en este roadmap un proveedor ni se confirman las condiciones actuales de los servicios citados en el PDF; su comprobación pertenece a la fase de viabilidad.

## Riesgos y mitigaciones

| Riesgo | Medida y fase |
| --- | --- |
| Fuente incompleta, cambiante o no apta para automatización | Validación previa, contrato reemplazable, estados parciales y prueba de humo; fases 0, 2 y 5 |
| Confundir anuncio/anunciante o clasificar por parecido de nombre | Identidad por fuente, IDs separados, conflictos explícitos y evidencia obligatoria; fases 1 y 3 |
| Falsos positivos por mención de marca | Revisión humana, razones visibles y estado Pendiente; fase 3 |
| Filtración de URLs sensibles | Sin envío automático; sanitización y evaluación previa de proveedores opcionales |
| Agotamiento de disco por medios | Límites, hashes, retención y control de espacio; fases 4 y 5 |
| Confundir reporte con retirada | Estados independientes y confirmación externa explícita; fase 4 |

## Próximo paso

Siguiente entrega: mejorar ficha de auditoria con contenido estructurado y navegacion, e incorporar historicos/correcciones/reportes a la interfaz. Primera interfaz Tkinter de Inicio y Auditoria implementada y verificada; aceptacion ergonomica, multimedia y filtros completos pendientes.


### Avance de configuracion

- [x] Cargar y validar perfiles/manifiestos JSON antes de consultar: campos obligatorios, pais ISO, booleanos, criterios, zona horaria y coherencia temporal.
- [x] Ejecutar criterios habilitados de varios perfiles y resolver salida respecto al manifiesto; validar escritura antes de la consulta.
- [ ] Completar edicion de perfiles desde UI y configuracion de todas las rutas (SQLite, evidencia, respaldos y logs).

### Avance de respaldo e identidad

- [x] Respaldo inicial SQLite mediante API consistente, hash, verificacion de integridad y restauracion en destino nuevo.
- [x] Identidad local declarada del analista y prioridad de --actor en importacion, respaldo y restauracion.
- [ ] Ampliar el respaldo a perfiles y activos de evidencia en fase 4.

### Avance de ingesta conectada

- [x] Guardar automaticamente cada consulta en JSON y SQLite con actor y cliente.
- [x] Generar resumen con nuevos anuncios, descartes, cobertura y errores de fuente/persistencia.
- [x] Conservar resultados ante fallos de fuente o cancelacion controlada y permitir reimportacion idempotente del JSON.
- [ ] Incorporar checkpoints incrementales para recuperacion ante terminacion abrupta del proceso.

### Avance de listas y cola

- [x] Cargar y validar tres listas JSON, alcances, duplicados y antecedentes requeridos.
- [x] Evaluar negra antes que marron, blanca por alcance y conflictos blanca/negra sin clasificacion automatica.
- [x] Incluir decisiones de cruce y cola determinista en resultados y resumen.
- [ ] Sincronizar listas con SQLite y resolver conflictos con auditoria administrativa.

### Avance de decisiones humanas

- [x] Abrir casos por anuncio, fuente y cliente sin duplicar el mismo contexto.
- [x] Clasificar Spam, Ataque y Pendiente con confirmacion de identidad, evidencia requerida para Ataque y auditoria transaccional.
- [x] Incorporar decisiones de listas SQLite al cruce de nuevas busquedas.
- [ ] Implementar correcciones justificadas, resolucion administrativa e importacion/exportacion masiva de listas.

### Avance de cola e historial de casos

- [x] Consultar cola actual y casos desde SQLite, con filtro por cliente y exclusiones por clasificacion.
- [x] Reabrir casos con confirmacion, justificacion y auditoria, conservando evidencia y antecedentes de otros casos.
- [x] Registrar reportes manuales con fecha, actor, referencia y estado externo separado de la clasificacion.
- [ ] Completar filtros por criterio, pais, fechas y anunciante e interfaz de dos pantallas.

### Avance de interfaz local

- [x] Primera interfaz Tkinter con Inicio y Auditoria, carga de manifiesto, identidad, ejecucion en segundo plano y cancelacion cooperativa.
- [x] Mostrar cola SQLite, conflictos y detalle textual; ejecutar Spam/Ataque/Pendiente con confirmaciones.
- [ ] Completar ficha multimedia, navegacion, historicos y acciones de correccion/reporte desde UI.


### Lista manual de ejecuciones

- [x] Agregar y editar pais/criterio, activar/desactivar y eliminar filas con confirmacion.
- [x] Ejecutar solo filas habilitadas con rango definido por Dias a revisar.
- [x] Guardar y cargar listas editables JSON, conservando estados habilitados/deshabilitados.


### Control de consultas lentas

- [x] Aislar el proveedor en proceso terminable, con limite total e inactividad sin anuncios.
- [x] Mostrar progreso de recepcion y filtrado; cancelar aunque el proveedor este esperando red.
- [x] Preservar resultados parciales y registrar timeout sin presentar ausencia garantizada de anuncios.


### Filtro temporal solicitado al servidor

- [x] Enviar startDate con min/max en todas las paginas y registrar diagnostico de solicitudes.
- [x] Detener paginacion con error explicito si los anuncios contradicen el intervalo, sin afirmar ausencia de resultados.
- [ ] Resolver equivalencia con Biblioteca manual: el endpoint probado ignora el rango aun con variables enviadas. No se considera validado el filtrado en servidor.
