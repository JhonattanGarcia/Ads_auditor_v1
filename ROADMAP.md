# Roadmap — Brand Threat Monitor

Actualizado: **17 de noviembre de 2026**.
Fuente funcional: `documentación/Requisitos_Funcionales_Brand_Threat_Monitor.pdf`, versión 1.0.

## Estado actual

Aplicación local en Python, SQLite y Tkinter con búsquedas configurables, resultados JSON, persistencia automática, listas, revisión humana, históricos, exportaciones y respaldos verificados. **El MVP todavía no está cerrado.**

La última verificación ejecutada pasó **113 pruebas**. Hay pruebas de integración con datos ficticios, comprobaciones de arranque de UI y consultas/restauraciones reales documentadas; esto no equivale a haber aprobado todos los criterios CA y escenarios E2E del documento funcional.

**Pendiente crítico del conector:** Meta devuelve anuncios fuera del rango aunque se envíe `startDate` en cada solicitud. Se detiene la consulta con `ServerDateFilterMismatch`; no se presenta ese resultado como una búsqueda vacía ni como cobertura validada. Ordenar por impresiones no permite detenerse cronológicamente al primer anuncio antiguo. Ver `docs/CONNECTOR_FEASIBILITY.md` y la sección de filtro temporal del README.

El desarrollo avanzó en varias fases en paralelo. Las casillas describen entregables concretos; una fase con pendientes no se considera terminada. Se eliminaron los anexos acumulativos que repetían tareas ya incorporadas a estas fases.

## Reglas vigentes

- Blanca y negra identifican anunciantes por fuente y `advertiser_id`; marrón identifica publicaciones por fuente y `ad_id`.
- Conflictos blanca/negra requieren resolución explícita. Sin conflicto: negra → blanca → marrón → desconocido.
- Los antecedentes priorizan anuncios nuevos, sin confirmar automáticamente fraude ni reportarlos.
- Clasificación, cambios de listas y auditoría se guardan transaccionalmente. Las correcciones conservan eventos y evidencia previa.
- Los reportes a Meta son manuales; sus estados externos son independientes de la clasificación.
- Las fechas de observación se distinguen de la fecha de inicio del anuncio; no se promete cobertura total.

## Preferencias incorporadas

- [x] Interfaz en inglés.
- [x] Control **Days to review**, predeterminado 1, con ventana inclusiva hasta hoy en `America/Bogota`.
- [x] Lista manual editable: Enabled, Country, Search criteria y Delete. Solo se ejecutan filas habilitadas.
- [x] Enabled aplica inmediatamente a la fila seleccionada; sin selección define el estado de la siguiente fila.
- [x] Guardado automático de lista, activaciones y días en `data/search_list.json`; restauración al abrir. Exportación manual opcional de una copia.
- [x] Sin controles de identidad del analista en UI. Auditoría gráfica con `local_operator`; CLI conserva opciones de actor explícito.

## Fase 0 — Viabilidad y decisiones técnicas

**Estado: validación parcial; fuente provisional.**

- [x] Ejecutar consultas reales de `pichincha / CO` y `chivo / SV`, investigar IDs y documentar diferencias con Biblioteca manual.
- [x] Definir contrato reemplazable, adaptador Meta y fuente ficticia para pruebas sin red.
- [x] Seleccionar Tkinter e implementar las dos pantallas principales y ventanas auxiliares; documentar la decisión técnica.
- [x] Enviar rango temporal en primera página y cursores sucesivos, con diagnóstico de solicitudes sin tokens.
- [x] Detectar respuesta incompatible con el rango y detener paginación conservando resultados recibidos.
- [ ] Conseguir un conector/endpoint que respete el filtro temporal y validar equivalencia con búsqueda manual y continuidad de paginación.
- [ ] Evaluar condiciones de consulta, privacidad y almacenamiento de material antes de seleccionar definitivamente la fuente.
- [ ] Acordar protocolo operativo de evidencia mínima y validar ergonomía con el analista.

Salida pendiente: fuente apta para el uso previsto, con límites medidos y condiciones evaluadas. Mientras tanto, los servicios pueden desarrollarse y probarse con datos ficticios, sin declarar resuelta la recolección real.

Trazabilidad: RF-003, RF-004, RF-009, RF-014; RNF-01, RNF-03, RNF-11.

## Fase 1 — Configuración, base local e integridad

**Estado: base operativa; configuración avanzada pendiente.**

- [x] Separar módulos de configuración, búsqueda, recolección, persistencia, listas, revisión, exportaciones, respaldo y UI. Algunos módulos reservados siguen sin implementación.
- [x] Crear esquema SQLite con migraciones, claves foráneas, índices, identidad por fuente y WAL.
- [x] Validar perfiles/manifiestos JSON: versión, campos, país ISO, criterios, activación, zona horaria y coherencia de fechas.
- [x] Construir URLs codificadas con país/criterio del perfil y rangos hoy, ventana inclusiva o fijo.
- [x] Permitir edición manual de búsquedas en UI y ejecución independiente por criterio.
- [x] Resolver rutas del manifiesto respecto a su archivo y comprobar escritura de salida antes de consultar.
- [x] Implementar transacciones, auditoría, actor interno y respaldo inicial SQLite.
- [ ] Completar configuración gráfica centralizada de todas las rutas: base, medios, exportaciones, respaldos y logs.
- [ ] Registrar un desglose explícito de diferencias entre URL original y efectiva, además de conservar ambas.

Trazabilidad: RF-001–007, RF-038, RF-041; RNF-02–05.

## Fase 2 — Recolección, ingesta y observaciones

**Estado: flujo conectado; equivalencia de fuente y recuperación incremental pendientes.**

- [x] Conectar búsqueda → `results.json` → SQLite → `run_summary.json`, con cliente y actor.
- [x] Registrar RUN_ID, URLs original/efectiva, filtros solicitados, versión, tiempos, cobertura, errores y conteos.
- [x] Deduplicar anuncios por fuente/ID, conservar primera/última observación y relacionar corridas y consultas.
- [x] Separar registros sin identidad/fecha verificable y diagnósticos de descarte del conjunto de anuncios aceptados.
- [x] Preservar resultados recibidos ante fallo de fuente o cancelación controlada; reimportar el mismo documento sin duplicar datos ni auditoría.
- [x] Ejecutar proveedor en proceso terminable: 120 segundos totales y 45 sin recibir anuncios; Stop no espera a que termine HTTP.
- [x] Mostrar progreso de recepción/filtrado y distinguir resultados parciales de fallos de persistencia.
- [ ] Añadir checkpoints incrementales para recuperar datos ante terminación abrupta antes del guardado final.
- [ ] Completar extracción/normalización de URLs de destino y tipos; actualmente se conserva payload y URL de Biblioteca, sin catálogo completo de destinos.
- [ ] Validar persistencia de datos brutos permitidos y conservar versiones históricas de creatividades cuando corresponda.

Los descartados por fecha se conservan como diagnóstico de la corrida; no se convierten automáticamente en anuncios/casos de auditoría.

Trazabilidad: RF-008–016, RF-040, RF-042; RNF-04, RNF-05, RNF-09.

## Fase 3 — Listas, cola y decisiones humanas

**Estado: revisión funcional; administración de listas pendiente.**

- [x] Cargar y validar blanca/negra/marrón JSON, alcance, duplicados, antecedentes y referencias requeridas para negra.
- [x] Combinar listas JSON con decisiones activas SQLite sin reescribir los archivos de entrada.
- [x] Detectar conflictos entre alcances aplicables, excluirlos de clasificación automática y priorizar negra sobre marrón.
- [x] Construir cola determinista con motivos y filtrar por cliente, país, criterio, anunciante exacto y fechas locales.
- [x] Abrir casos por anuncio/fuente/cliente; aplicar Spam, Ataque y Pendiente con auditoría atómica y confirmaciones distintas.
- [x] Exigir archivo de evidencia existente, hash y límite inicial de 20 MiB para Ataque.
- [x] Corregir con justificación y reapertura, conservando evidencia y antecedentes sustentados por otros casos.
- [x] Navegar anterior/siguiente y conservar selección o posición cercana al actualizar la cola.
- [x] Abrir deliberadamente el anuncio en Biblioteca sin abrir destinos sospechosos automáticamente.
- [ ] Implementar resolución administrativa de conflictos, mantenimiento de whitelist e importación/exportación masiva CSV/JSON con respaldo y procedencia.
- [ ] Incorporar revisión extraordinaria de blancos/marrones, filtros por estado/lista y ordenación configurable completa.
- [ ] Optimizar consultas y paginación para volumen alto; los filtros iniciales procesan contextos locales en memoria.

Trazabilidad: RF-017–031, RF-041, RF-043, RF-044; RN-01–05; RNF-06, RNF-07, RNF-10.

## Fase 4 — Evidencia, históricos, exportación y respaldos

**Estado: históricos, exportación y respaldo operativos; multimedia pendiente.**

- [x] Mostrar ficha textual con IDs, anunciante, contenido, URLs/referencias de medios y ausencias explícitas.
- [x] Consultar históricos de corridas/casos, eventos, evidencia y reportes desde UI y CLI.
- [x] Registrar reportes manuales con fecha zonificada, referencia, notas y estado externo, sin inferir aceptación o retirada.
- [x] Aplicar filtros a corridas y casos: fechas inclusivas de inicio de corrida u observación, respectivamente.
- [x] Exportar expediente JSON/CSV con contenido obtenido, consultas, observaciones, URLs, eventos, evidencia referenciada y reportes.
- [x] Proteger celdas CSV frente a fórmulas y evitar sobrescritura de exportaciones existentes.
- [x] Crear respaldo completo de SQLite, perfiles, listas, búsquedas guardadas y evidencia local interna/externa referenciada.
- [x] Verificar hashes, integridad y evidencia; restaurar en carpeta nueva y ajustar rutas de evidencia con auditoría. Probado con una restauración real.
- [ ] Implementar previsualización multimedia local con límites de tipo/tamaño y gestión controlada de archivos permitidos.
- [ ] Completar custodia de evidencia: copia administrada, verificación continua, retención y tolerancia a archivos ausentes.
- [ ] Entregar Listado URLs y vista completa de anunciante con relaciones, reincidencias e historial.
- [ ] Consolidar métricas de revisiones/reportes posteriores sin reescribir resúmenes históricos de búsquedas.
- [ ] Añadir controles gráficos de respaldo/restauración y reubicación de rutas personalizadas.
- [ ] Ofrecer PDF opcional y expediente autocontenido con archivos de evidencia, además de sus referencias.

El respaldo completo actual contiene datos y no el código; se opera por CLI. SQLite es una instantánea transaccional; perfiles y evidencia se verifican individualmente, sin transacción global del sistema de archivos. Ver README para exclusiones y restauración.

Trazabilidad: RF-015, RF-025, RF-032–040; RNF-02, RNF-06–09.

## Fase 5 — Validación integral y cierre del MVP

**Estado: pruebas parciales continuas; aceptación integral pendiente.**

- [x] Mantener pruebas de regresión para perfiles, URLs, listas, persistencia, cancelación, revisiones, reportes, exportación, filtros y respaldos.
- [x] Verificar casos de atomicidad, reimportación idempotente, conservación de historia y restauración con datos reproducibles.
- [ ] Mapear y ejecutar formalmente CA-01–15 y E2E-A/B/C; registrar evidencia por criterio y pendientes, sin equiparar cantidad de pruebas con aceptación funcional.
- [ ] Validar fuente real y añadir una prueba de humo reproducible que detecte rupturas del conector.
- [ ] Completar revisión de logs/secretos, medios, retención, privacidad y navegación.
- [ ] Revisar accesibilidad: teclado, contraste, etiquetas, estados y mensajes comprensibles sin depender del color.
- [ ] Actualizar documentación consolidada y realizar piloto de extremo a extremo con aceptación del analista.

Salida: criterios del MVP aprobados, límites conocidos documentados y recuperación verificada. No se marca el MVP terminado mientras la recolección no respete el alcance temporal acordado.

Trazabilidad: RF-001–044; CA-01–15; E2E-A/B/C; RNF-01–12.

## Próximas entregas

1. Previsualización de evidencia multimedia local, con controles de tipo/tamaño y sin carga automática de destinos externos.
2. Administración de listas/conflictos e intercambio masivo validado.
3. Listado de URLs, detalle de anunciante y métricas de revisión/reportes.
4. Completar validación del conector temporal y aceptación integral. Esta validación puede adelantarse y condiciona la declaración de cobertura y el cierre del MVP.

## Decisiones y límites abiertos

| Tema | Estado |
| --- | --- |
| Fuente Meta | `meta-ads-collector` 1.7.2, provisional; rango enviado pero no respetado en pruebas. Sin equivalencia validada con Biblioteca manual. |
| Interfaz | Tkinter operativo; ergonomía y accesibilidad pendientes de aceptación completa. |
| Listas | Negra global; blanca por alcance explícito; marrón por alcance del caso. Conflictos se detectan, sin resolución administrativa todavía. |
| Evidencia mínima | Archivo local verificable requerido técnicamente; protocolo de atribución y categorías aún por acordar. |
| Días de búsqueda | UI predeterminada 1; modifica el rango de esa ejecución. Las fechas no garantizan cobertura si la fuente las ignora. |
| Identidad | Sin controles en UI por solicitud del usuario; identificador fijo de auditoría y opciones CLI conservadas. |
| Retención y volumen | Pendientes política completa, límites de disco y optimización para mayor volumen. |

## Evolución opcional y fuera de alcance

- [ ] Programación periódica, correlaciones explicables y priorización más rica tras el piloto.
- [ ] Reputación externa bajo demanda, previa evaluación de licencias, cuotas y sanitización.

Fuera del MVP: denuncias automáticas a Meta, bloqueo de páginas, atribución legal, navegación activa automática a sitios sospechosos, IA, reconocimiento avanzado de logos y operación distribuida. No se garantiza cobertura total ni recuperación retrospectiva no permitida por la fuente.


Entrega del 17 de noviembre de 2026: previsualizacion y copia administrada de imagenes locales disponibles desde auditoria e historicos. Ver README para formatos, limites y exclusiones. El filtrado temporal real de Meta sigue pendiente.


Entrega del 17 de noviembre de 2026: Manage lists y comandos administrativos para whitelist, desactivacion y resolucion explicita de conflictos JSON/SQLite. Nueva migracion de exclusiones y respaldo completo previo a su aplicacion. La equivalencia temporal del conector sigue pendiente.


Entrega del 17 de noviembre de 2026: intercambio masivo JSON/CSV disponible en UI y CLI, con preview, proteccion CSV reversible, reimportacion idempotente, validacion de antecedentes y respaldo previo. Los conflictos rechazan el lote y no se resuelven automaticamente. Fuente temporal de Meta pendiente de validacion.


Ajuste de interfaz: Ad review carga automaticamente resultados persistidos al inicio y al abrir la pesta?a, conserva prioridades y ordena por observacion reciente. Distribucion inferior corregida y comprobada a 850x600; diagnosticos extensos dentro de la ficha desplazable. No se modifica la limitacion temporal de Meta.


Ajuste de analisis: presentacion completa de datos como campos legibles, incluyendo estructuras anidadas, campos adicionales de fuente y ejecuciones relacionadas. All information permite explorar y copiar valores completos sin mostrar la estructura JSON; historicos y diagnosticos usan la misma presentacion.
