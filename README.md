# Ads_auditor_v1 ? Brand Threat Monitor

Aplicacion local en Python y SQLite para buscar anuncios de Meta, priorizar posibles suplantaciones de marcas y registrar revisiones humanas. Los reportes a Meta son manuales.

## Estado

Version en desarrollo: busquedas, JSON, SQLite, listas, revision por comandos y primera interfaz de escritorio operativos. Persisten limites de cobertura temporal y funciones pendientes del roadmap.

## Preparacion

Requiere Python 3.11 o superior. En PowerShell, desde la raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m brand_threat_monitor --help
.\.venv\Scripts\python.exe -m brand_threat_monitor --version
```

Tras instalar, tambien esta disponible el comando `brand-threat-monitor` en el entorno virtual. No hay dependencias de ejecucion externas por ahora.

## Organizacion

- `src/brand_threat_monitor/`: codigo organizado por responsabilidad.
- `profiles/example.json`: perfil ficticio de referencia; perfiles reales en `profiles/local/`.
- `data/`: base, evidencia, exportaciones, respaldos y logs locales excluidos de Git.
- `tests/`: ubicaciones para pruebas unitarias, integracion y escenarios E2E.
- `docs/ARCHITECTURE.md`: mapa de modulos y responsabilidades.
- `ROADMAP.md`: fases y criterios de entrega.
- `URL_SEARCH_SPEC.md`: reglas propuestas para adaptar URLs desde JSON.

El PDF original permanece en `documentaci?n/`, excluido de Git. La zona horaria predeterminada es America/Bogota y la ventana predeterminada es el dia actual. Estas reglas aun deben implementarse en el motor de busquedas.

## Primera busqueda real

Instalar o actualizar el entorno con ` .\.venv\Scripts\python.exe -m pip install -e . `.

```powershell
.\.venv\Scripts\python.exe ejecutar_busqueda.py --dry-run
.\.venv\Scripts\python.exe ejecutar_busqueda.py --max-scan 30 --actor local_operator
```

Usa `profiles/example.json`: Pichincha, Colombia y dia actual en America/Bogota. `--profile ruta.json` selecciona otro perfil con exactamente un criterio habilitado. `--url "URL"` cambia la plantilla; el perfil sigue determinando pais, criterio y rango. `--output ruta.json` cambia el destino.

La salida predeterminada es `data/results/<run_id>/results.json`: URL original/efectiva, rango, anuncios, observaciones, descartes por fecha, registros incompletos y errores. La salida se guarda automaticamente en SQLite y genera run_summary.json; el cruce con listas sigue pendiente.

El adaptador usa meta-ads-collector 1.7.2, que consulta endpoints internos de Meta. No soporta enviar el rango temporal: filtra localmente la fecha de inicio de los anuncios recibidos, convirtiendola a la zona del perfil; excluye fechas ausentes o sin zona verificable. Solo admite las opciones de la URL de ejemplo y declara la opcion territorial no verificada. Inspecciona hasta --max-scan anuncios (1 a 100), por lo que la cobertura siempre se declara parcial. Cero resultados no demuestra ausencia de anuncios. Los errores conservan los resultados recibidos y generan codigo de salida distinto de cero.

Pruebas sin red:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -v
```


## Base local e importacion

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor init-db
.\.venv\Scripts\python.exe -m brand_threat_monitor import-results data/results/diagnostic_100/results.json --actor local_operator
```

La base se crea en `data/database/monitor.sqlite3` (excluida de Git). Ambos comandos admiten `--database ruta.sqlite3`. La importacion requiere un actor explicito, preserva el JSON de la corrida y guarda anuncios aceptados, observaciones y procedencia de consulta. Reimportar el mismo documento no duplica datos ni eventos; un RUN_ID con contenido distinto se rechaza. Un fallo revierte toda la corrida.

Los anuncios excluidos por fecha permanecen como diagnostico dentro del payload de corrida; no se incorporan a la tabla ads. Por eso importar un resultado con ads vacio registra la corrida pero no crea anuncios. La consulta de diagnostico de 68 anuncios es un ejemplo de este caso.

El esquema incluye listas, casos, evidencia y reportes para las siguientes entregas; sus servicios y UI aun no estan implementados. La importacion actual admite la salida monobusqueda de ejecutar_busqueda.py. No importa automaticamente los tres JSON de listas ni realiza respaldos. La exclusion blanca/negra se garantiza por fuente, anunciante y scope exacto; conflictos entre alcances distintos se resolveran en el servicio de listas.


## Perfiles y busquedas multiples

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor validate-profiles profiles/searches.json
.\.venv\Scripts\python.exe ejecutar_busqueda.py --manifest profiles/searches.json --dry-run
.\.venv\Scripts\python.exe ejecutar_busqueda.py --manifest profiles/searches.json --max-scan 30 --actor local_operator
```

La carga y validacion de perfiles esta implementada. Se ejecuta una consulta por criterio habilitado, con salida configurada en el manifiesto. Consultar profiles/README.md para reglas de rutas y activacion. La interfaz y los servicios de listas siguen pendientes.


## Analista y respaldo SQLite

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor set-operator jhonattan
.\.venv\Scripts\python.exe -m brand_threat_monitor whoami
.\.venv\Scripts\python.exe -m brand_threat_monitor backup-db
.\.venv\Scripts\python.exe -m brand_threat_monitor restore-db data/backups/ID_DEL_RESPALDO --target data/database/restored.sqlite3
```

La identidad declarada se guarda en data/operator.json, fuera de Git. No es autenticacion. import-results, backup-db y restore-db admiten --actor para sobrescribirla en esa operacion; sin identidad configurada ni argumento explicito se bloquea la operacion.

backup-db usa la API de respaldo SQLite, incluye datos confirmados en WAL y comprueba integridad y claves foraneas. Cada carpeta UUID contiene database.sqlite3 y manifest.json con hash SHA-256, actor, fecha y alcance. restore-db comprueba el hash e integridad y exige un destino nuevo sin WAL/SHM; registra el actor de restauracion en audit_log de la copia. Nunca reemplaza la base activa. El manifiesto no tiene firma criptografica: el hash detecta alteraciones respecto al manifiesto, no autentica su autor.

Alcance actual: solo SQLite. Perfiles JSON, identidad, resultados y archivos de evidencia no estan incluidos; el respaldo completo de la fase 4 sigue pendiente. Respaldos y restauraciones permanecen en data/, excluido de Git.


## Flujo conectado: busqueda, SQLite y resumen

El ejecutor valida perfiles, identifica al analista y comprueba la base antes de consultar. --actor permite indicar analista para esta ejecucion; si se omite usa la identidad declarada con set-operator. --database cambia la ruta SQLite.

Por cada criterio guarda results.json y run_summary.json en data/results/<run_id> e importa la corrida automaticamente en SQLite. Con --output archivo.json, el resumen se guarda como archivo_summary.json (results.json conserva el nombre run_summary.json). Los anuncios aceptados se deduplican por fuente/ID; las observaciones quedan vinculadas a su corrida y cliente. El contador new_ads se calcula en la transaccion de importacion.

Los resultados JSON se guardan antes de importar. Si SQLite falla despues de la consulta, el resumen indica persistence.status=failed y el JSON permite reintentar con import-results. No existe una transaccion unica entre archivos y SQLite: si se interrumpe el proceso, un resumen pending requiere verificar/reimportar su JSON. Si se repite exactamente la importacion no se duplican anuncios ni eventos. Un corte abrupto durante la consulta aun puede perder datos que solo estaban en memoria; no hay checkpoints incrementales.

Los errores de fuente y la cancelacion controlada conservan los resultados recibidos hasta ese momento. Las metricas de listas y revisiones quedan null hasta implementar esos servicios, sin inventar ceros. Las limitaciones de cobertura y filtrado temporal local siguen vigentes.


## Cruce de listas y cola inicial

Cada busqueda valida y carga lists/whitelist.json, blacklist.json y brownlist.json antes de consultar (otra ruta con --lists-dir). La evaluacion se incorpora a results.json y el resumen incluye cola y conteos. Conflictos blanca/negra requieren revision administrativa; no se clasifican automaticamente. Ver lists/README.md para el formato de entradas y alcances.

La cola todavia no es una pantalla interactiva ni crea decisiones humanas. Gestion transaccional de listas en SQLite, edicion de casos y correcciones siguen pendientes.


## Revision humana por comandos

Abrir un caso de un anuncio existente en SQLite (devuelve case_id):

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor open-case meta_ad_library ID_ANUNCIO --client-id cliente_pichincha --actor analista
.\.venv\Scripts\python.exe -m brand_threat_monitor review-case ID_CASO pending --reason "Falta evidencia" --actor analista
.\.venv\Scripts\python.exe -m brand_threat_monitor review-case ID_CASO spam --confirm-id ID_ANUNCIO --reason "Irrelevante" --actor analista
.\.venv\Scripts\python.exe -m brand_threat_monitor review-case ID_CASO attack --confirm-id ID_ANUNCIANTE --evidence-file ruta/evidencia.txt --reason "Motivo documentado" --actor analista
```

Los ejemplos Spam y Ataque son alternativas; no ejecutar ambos sobre un caso clasificado. --database permite otra base. open-case reutiliza el caso del mismo anuncio/fuente/cliente; omitir --client-id crea contexto global. Spam agrega marron con el alcance del caso. Ataque agrega negra global, requiere ID de anunciante conocido y archivo de evidencia de hasta 20 MiB; guarda su ruta absoluta y hash sin abrirlo ni copiarlo. Conservar el archivo original: aun no hay custodia ni copia administrada de evidencia.

Cada decision y sus efectos se guardan en una transaccion con audit_log antes/despues, actor y motivo. Se bloquea una reclasificacion directa de Spam/Ataque; Pendiente puede clasificarse despues. La correccion justificada esta disponible mediante correct-case; la resolucion administrativa de conflictos sigue pendiente. No se reporta nada automaticamente a Meta.

review-case comprueba conflictos con whitelist de SQLite y de los JSON en --lists-dir (predeterminado lists/). Conservadoramente bloquea Ataque si el anunciante tiene cualquier autorizacion activa, porque Ataque crea blacklist global. Las busquedas combinan JSON con listas activas SQLite al iniciar; el estado SQLite prevalece sobre entradas del mismo tipo/identidad/scope exacto y conserva conflictos entre tipos. Los JSON no se reescriben ni se importan masivamente a tablas.

Las decisiones previas no modifican los resultados y resumen historicos. Una nueva busqueda calcula otra evaluacion. La cola inicial aun no filtra casos ya revisados ni reacciona durante un lote a cambios simultaneos de listas; la cola de trabajo interactiva sera la siguiente integracion.


## Cola, historial, correcciones y reportes manuales

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor review-queue
.\.venv\Scripts\python.exe -m brand_threat_monitor list-cases --client-id cliente_pichincha
.\.venv\Scripts\python.exe -m brand_threat_monitor show-case ID_CASO
.\.venv\Scripts\python.exe -m brand_threat_monitor correct-case ID_CASO --confirm-case-id ID_CASO --reason "Justificacion de la correccion" --actor analista
.\.venv\Scripts\python.exe -m brand_threat_monitor record-report ID_CASO --reported-at "2026-11-14T15:00:00-05:00" --status sent --reference "REFERENCIA_EXTERNA" --reason "Reporte realizado manualmente" --actor analista
```

review-queue consulta anuncios observados en SQLite, combina listas actuales y omite casos Spam/Ataque del contexto o globales. Admite --client-id y --lists-dir. No crea casos automaticamente: un elemento puede tener case_id null hasta open-case. list-cases admite --status. show-case incluye anuncio, eventos, evidencias y reportes. Todos admiten --database.

correct-case reabre en pending_review y desactiva efectos propios registrados, conservando las entradas historicas, eventos y evidencias. Si otro caso Ataque del mismo anunciante mantiene un antecedente, conserva blacklist y vincula ese caso en lugar de eliminarlo. Las entradas JSON externas o entradas preexistentes no creadas por el caso no se eliminan: pueden seguir afectando la cola hasta su resolucion administrativa. La nueva clasificacion se hace mediante review-case como accion posterior explicita.

record-report solo registra una accion externa; no envia reportes ni altera la decision del caso. Estados: sent, awaiting_response, action_confirmed y unknown. action_confirmed exige referencia externa y notas; la aplicacion no verifica automaticamente esa confirmacion. La fecha debe incluir zona y no ser futura. Cada registro es un evento independiente con actor y auditoria; no elimina reportes anteriores. La plataforma es Meta por contexto de esta version. El resumen historico de una busqueda no se reescribe con revisiones posteriores.

La consulta real de review-queue puede estar vacia si los JSON importados no contienen anuncios aceptados por fecha, aunque incluyan diagnostico de anuncios descartados. La UI y filtros adicionales por criterio/fecha quedan pendientes.


## Interfaz de escritorio

Desde la raiz del proyecto:

```powershell
.\.venv\Scripts\python.exe iniciar_interfaz.py
```

Tambien: python -m brand_threat_monitor.ui.app --workspace RUTA_PROYECTO. Tkinter se incluye con la instalacion habitual de Python para Windows; no se requiere servidor web. --check construye y cierra la ventana para verificar arranque sin consultas.

Inicio / busquedas: cargar profiles/searches.json, revisar criterios habilitados, elegir Dias a revisar (1 por defecto) y ejecutar. El control define una ventana inclusiva hasta hoy y sustituye el rango del perfil solo para esta ejecucion; conserva las rutas del manifiesto. No solicita identidad; la auditoria usa local_operator. Detener solicita cancelacion cooperativa, y cerrar durante una busqueda pide esperar a que se guarden los resultados. El hilo de consulta no modifica widgets directamente.

Auditoria: actualizar cola, filtrar por cliente, seleccionar anuncio y revisar campos obtenidos y casos previos. Spam y Ataque usan confirmaciones distintas; Ataque exige archivo local de evidencia. Pendiente pide motivo. Abrir anuncio lleva deliberadamente a Biblioteca, sin navegar a destinos del anuncio. Los conflictos se muestran, pero la interfaz impide clasificarlos. Los cambios van a SQLite y auditoria mediante los mismos servicios de la CLI.

Primera version de interfaz: detalle textual del payload, sin renderizar imagenes/videos; no hay editor de perfiles, botones de correccion/reporte, navegacion anterior/siguiente ni historicos completos. Esas operaciones siguen disponibles por CLI cuando estan implementadas. La cola puede estar vacia si no hay anuncios aceptados por el filtro temporal: los descartados del diagnostico no se convierten en casos automaticamente.


## Lista manual editable de ejecuciones

La interfaz permite agregar consultas sin preparar JSON: escribir Country (ISO de dos letras), Criterion, marcar Enabled y pulsar Add. La tabla muestra Enabled / Country / Criterion / Delete. Un clic en [X]/[ ] alterna la activacion; Delete solicita confirmacion. Seleccionar una fila carga sus campos; editar y pulsar Update selected guarda sus cambios. Espacio alterna habilitacion y la tecla Delete elimina la fila seleccionada.

Run searches usa exclusivamente las filas habilitadas y Days to review (1 por defecto). CO/pichincha habilitada y BR/bradesco deshabilitada producen una sola consulta para Colombia. Sin filas activas, no inicia la consulta. La lista se bloquea para cambios durante la ejecucion.

Save search list exporta el formato editable_search_list, incluidos estados deshabilitados. Load search JSON acepta este formato o el manifiesto existente. Las filas deshabilitadas de los perfiles cargados quedan visibles para reactivarlas; entradas completas deshabilitadas en el manifiesto se omiten segun su contrato. Guardar no modifica los archivos de origen; es necesario guardar antes de cerrar para conservar cambios. Al cargar una lista editable, la salida vuelve a data/results del proyecto; los manifiestos conservan su salida configurada. Days to review de la ventana gobierna cada ejecucion.


## Guardado automatico de la lista de busquedas

La lista de ejecuciones se guarda automaticamente en data/search_list.json (fuera de Git) al agregar, editar, activar/desactivar o eliminar filas y al cambiar un valor valido de Days to review. Al abrir la interfaz se restaura esa lista, incluidos deshabilitados, dias y carpeta de salida. No es necesario exportar para conservar las busquedas. Este comportamiento sustituye la indicacion anterior de guardar manualmente antes de cerrar.

Enabled aplica inmediatamente a la fila seleccionada; sin seleccion define el estado para la proxima fila agregada. Los cambios de pais/criterio siguen usando Update selected search. Export search list crea una copia opcional de la configuracion para compartir o respaldar; no guarda resultados. Los resultados siguen en data/results/<run_id>/ y en SQLite. Cargar un JSON reemplaza la lista de trabajo actual y la guarda automaticamente.


## Esperas y cancelacion de consultas

El recolector externo puede repetir peticiones, refrescar sesiones y recorrer hasta 25 paginas vacias antes de fallar. max_retries del cliente no limita todos los bucles internos. Ademas, revisar un dia sigue requiriendo consultar anuncios de otras fechas porque el filtro es local. Esto puede aparentar un bloqueo aun con pocos anuncios visibles manualmente.

El adaptador predeterminado ahora ejecuta cada consulta en un proceso separado. Limites: 120 segundos totales y 45 segundos sin recibir otro anuncio, incluyendo inicializacion, reintentos y paginas vacias. Si se exceden, termina el proceso, conserva los anuncios recibidos y registra CollectorTimeout. El limite es de seguridad operativa; no significa que no existan mas resultados. Una consulta vacia que termina normalmente no se etiqueta como timeout.

Stop comprueba cancelacion cada 0.1 segundos en el supervisor y termina el proceso de consulta; ya no espera a que finalice HTTP. El guardado local posterior puede tardar adicionalmente. La barra de estado muestra segundos, anuncios recibidos y conteos del filtro temporal. El limite de tiempo y el limite de inactividad se guardan en search_limits del JSON. Este comportamiento sustituye las notas anteriores sobre cancelacion exclusivamente entre resultados. La CLI utiliza el mismo adaptador acotado.


## Solicitud de filtro temporal al servidor (15 noviembre 2026)

El adaptador aplica startDate={min,max} a las variables de AdLibrarySearchPaginationQuery en cada pagina mediante una extension por instancia, sin editar la dependencia instalada. El rango pasa del perfil al proceso aislado y las solicitudes se registran en connector_stats.date_filter_requests (fechas y presencia de cursor, sin tokens). El maximo vacio se representa como null en la extension; los perfiles actuales calculan ambos limites.

Prueba real chivo/SV, 14 a 15 noviembre: Meta acepto la solicitud sin error GraphQL pero devolvio 30 anuncios fuera del intervalo en cuatro solicitudes. Por tanto no se declara que el servidor respete el filtro. Diagnostico inicial: data/results/server_date_validation/results.json.

Se incorpora deteccion ServerDateFilterMismatch: si llega un anuncio cuya fecha de inicio esta fuera del intervalo tanto en fecha de la fuente como en zona local, se detiene la consulta, conserva los anuncios ya aceptados y registra temporal_filter_status=server_filter_not_respected. No interpreta este caso como ausencia de anuncios ni sigue paginando con un filtro ignorado. Si solo difiere el dia por zona horaria, se conserva la comprobacion local sin afirmar incompatibilidad del servidor.

La prueba posterior se detuvo tras el primer anuncio incompatible y una sola solicitud: data/results/server_date_guard/results.json. El filtrado temporal real sigue pendiente de un endpoint que lo respete; orden por impresiones no permite cortes cronologicos. Los limites de tiempo y cancelacion siguen activos. Este comportamiento sustituye el filtrado exclusivamente local descrito en secciones anteriores.


## Historial y navegacion desde la interfaz

La ficha de Ad review presenta anunciante, texto obtenido, URLs y referencias de medios en secciones. No carga sitios ni descarga/ejecuta multimedia. Previous y Next recorren la cola sin clasificar; al actualizar se conserva el anuncio seleccionado o la posicion mas cercana si ya salio de la cola.

History (Inicio) o History / corrections / reports (Auditoria) abre una ventana auxiliar con Search runs y Review cases. Search runs muestra corridas y su JSON historico. Review cases filtra por Client ID y presenta caso, evidencia, eventos y reportes. No se solicita identidad: las operaciones graficas usan local_operator.

Correct and reopen case exige motivo y confirmacion; invoca el servicio transaccional existente y actualiza la cola conservando historia. Record a manual report permite fecha ISO con zona, referencia, notas y estado externo. Solo registra reportes ya realizados fuera de la aplicacion, nunca los envia. action_confirmed exige referencia externa; no se verifica automaticamente la respuesta de Meta. Los controles y correcciones historicas no estan disponibles durante una busqueda en curso.

La multimedia sigue como referencia textual; previsualizacion, filtros completos y exportacion de expedientes siguen pendientes. La incompatibilidad de filtro temporal del endpoint no esta resuelta por esta entrega.


## Exportacion de expedientes por caso

En History / Review cases, seleccionar un caso y pulsar Export JSON o Export CSV. Tambien por comando:

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor export-case ID_CASO --format json --output data/exports/caso.json
.\.venv\Scripts\python.exe -m brand_threat_monitor export-case ID_CASO --format csv --output data/exports/caso.csv
```

El expediente incluye caso, contenido obtenido del anuncio, ID del anunciante, observaciones con consulta/pais/URLs y cobertura de corrida, URLs registradas, referencias y hashes de evidencia, reportes manuales y eventos antes/despues. Las lecturas se realizan en una instantanea SQLite consistente. Las observaciones se limitan al cliente del caso cuando existe ese contexto. El anuncio es la ultima representacion persistida; no se reconstruyen versiones historicas de creatividades que no se almacenaron.

JSON conserva los valores originales. CSV utiliza section, record, field y value para representar los registros relacionados, con UTF-8 BOM para compatibilidad con Excel. Los valores con prefijos de formula reciben un apostrofo de proteccion; los objetos/listas se serializan como JSON dentro de la celda. No se crean capturas ni se descargan medios. Los archivos de evidencia solo se referencian y no se comprueba su existencia actual ni se copian al expediente.

Las exportaciones no sobrescriben archivos existentes; elegir otro nombre. Una cancelacion del selector no exporta nada. Esta operacion es de lectura y no cambia clasificaciones ni audit_log; exported_at identifica cuando se genero el documento. Exportar un reporte no implica que Meta lo haya aceptado. PDF y paquetes autocontenidos de evidencia siguen pendientes.


## Filtros de cola e historicos

Ad review e History ofrecen Country, Search criteria (contains), Advertiser ID (exact), From y To. Apply filters o Enter aplica los valores; Clear filters limpia esos cinco campos, conservando el filtro independiente Client ID. Los valores permanecen al navegar o actualizar en la misma ventana; no se guardan entre sesiones.

Country valida ISO alfa-2 y no distingue mayusculas. Search criteria busca una subcadena literal sin distinguir mayusculas (no es SQL ni expresion regular). Advertiser ID requiere coincidencia exacta. Los filtros se combinan sobre una misma observacion/consulta: no se mezclan pais de una observacion con criterio de otra. Los casos por cliente solo usan observaciones de su contexto.

From/To aceptan YYYY-MM-DD, con extremos inclusivos y dia local America/Bogota. Cola y casos filtran por fecha observada; corridas por fecha de inicio. No representan fecha de publicacion del anuncio ni amplian la cobertura del conector. En historicos los filtros se aplican a ambas pestanas; los casos sin observaciones asociadas no coinciden con filtros activos. Una corrida sin anuncios puede coincidir por pais/criterio/fecha, pero no por anunciante. Los archivos exportados siguen siendo expedientes completos del caso seleccionado, no un recorte del filtro visual.

Ejemplos por comandos:

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor review-queue --country CO --criterion pichincha --date-from 2026-11-14 --date-to 2026-11-17
.\.venv\Scripts\python.exe -m brand_threat_monitor list-cases --client-id cliente_pichincha --advertiser-id ID_EXACTO
.\.venv\Scripts\python.exe -m brand_threat_monitor list-runs --country SV --criterion chivo
```

La implementacion inicial filtra los contextos locales en memoria; paginacion de tablas y optimizacion de consultas para volumen alto siguen pendientes.


## Respaldo completo de datos locales

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor backup-workspace
.\.venv\Scripts\python.exe -m brand_threat_monitor restore-workspace data/backups/ID_RESPALDO --target data/restored_workspace
```

backup-workspace admite --workspace, --directory y --actor (local_operator por defecto). Incluye la instantanea consistente de SQLite, JSON bajo profiles/ y lists/, data/search_list.json si existe y todos los archivos de data/evidence/. Tambien incluye archivos locales referenciados por evidence.local_path aunque esten fuera del proyecto. Si falta evidencia referenciada o no coincide con el hash almacenado, el respaldo falla sin publicar una carpeta final incompleta.

El manifiesto version 2.0 enumera archivos, tamanos y hashes SHA-256, mas el mapa de evidencia. No incluye codigo, entorno virtual, logs, exports, resultados JSON separados ni identidad declarada del operador. Las corridas guardadas en SQLite si se conservan. Los perfiles pueden contener informacion sensible: el respaldo es local y no esta cifrado; permanece fuera de Git bajo data/backups/.

restore-workspace exige un directorio que no exista. Verifica hashes, integridad SQLite, claves foraneas y evidencia frente a sus hashes en la base. Rechaza rutas ajenas a los directorios admitidos, traversal, dispositivos Windows y enlaces/junctions. No reemplaza la base ni archivos del proyecto activo. Ajusta evidence.local_path y la salida de la lista editable hacia el destino nuevo y agrega un evento de restauracion; el historial original conserva sus referencias anteriores.

La restauracion contiene datos, no codigo. Para inspeccionarla con la aplicacion instalada:

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor.ui.app --workspace data/restored_workspace
```

Las rutas absolutas personalizadas dentro de otros perfiles/manifiestos no se reescriben automaticamente; revisarlas antes de ejecutar busquedas en la copia. Mantener sin escrituras simultaneas los perfiles/listas/evidencias durante el respaldo: SQLite es una instantanea transaccional y cada archivo se verifica al copiar, pero no existe una transaccion global de base y sistema de archivos. Los hashes no son una firma del manifiesto.

Los comandos backup-db/restore-db siguen disponibles para respaldos solo SQLite version 1. Esta entrega se opera por CLI; botones de respaldo completo en UI siguen pendientes.


## Previsualizacion de imagenes locales

Ad review y History / Review cases incluyen Local evidence. Abrirlo desde la cola crea o reutiliza el caso del anuncio/contexto (sin clasificar); abrirlo desde historicos usa el caso seleccionado. Attach local image valida el archivo, exige una nota y guarda una copia original bajo data/evidence/ con hash SHA-256 y evento de auditoria. El archivo de origen permanece intacto. La copia se elimina si falla la transaccion de registro.

Preview selected image valida el hash registrado y muestra una miniatura de hasta 640x480, con formato, dimensiones originales y tamano. El selector no carga imagenes automaticamente; cambiar seleccion limpia la vista. No se consulta red, no se abren URLs/rutas de red ni se ejecuta un visor externo.

Formatos admitidos por contenido: PNG, JPEG, WebP y GIF. Limite de archivo 20 MiB, 20 millones de pixeles y 12000 pixeles por dimension. Los archivos corruptos, enlaces/junctions, imagenes incompatibles y hashes alterados bloquean la vista. GIF muestra solo el primer fotograma; videos, PDF y otros documentos siguen como referencias sin reproduccion.

Actualizar el entorno existente para instalar Pillow:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

Los archivos adjuntos se incluyen en los respaldos completos. Los expedientes JSON/CSV conservan sus referencias y hashes; no incluyen el binario. El archivo usado por review-case attack conserva el comportamiento previo de referencia externa: solo Attach local image crea la copia administrada de imagen. Gestion de video, descargas remotas permitidas y retencion siguen pendientes. La documentacion de Image.open/verify/thumbnail esta en https://pillow.readthedocs.io/en/stable/reference/Image.html.


## Administracion y conflictos de listas

Manage lists en Search setup muestra las entradas activas efectivas de JSON y SQLite, con fuente, ID, alcance, origen y motivo. Authorize advertiser crea whitelist con confirmacion y motivo; Client ID vacio significa alcance global y requiere confirmar ese efecto. No autoriza si existe blacklist que se solape: primero debe desactivarse o resolverse explicitamente. La inclusion negra sigue requiriendo caso y evidencia mediante Flag advertiser.

Deactivate selected conserva historia y desactiva la entrada del alcance seleccionado. Si proviene de JSON, registra una exclusion en SQLite en lugar de editar el archivo. Esa entrada JSON no reaparece en los siguientes cruces, aunque permanezca activa en el archivo original. Una decision nueva y deliberada de SQLite puede volver a crear una entrada activa. No hay borrado automatico de antecedentes ni cambios en clasificaciones historicas.

Resolve conflict usa Source, Advertiser ID y el contexto Client ID. Yes conserva whitelist; No conserva blacklist; Cancel no cambia nada. Desactiva todas las entradas opuestas que aplican a ese contexto. Si alguna es global, su desactivacion afecta tambien otros clientes; la confirmacion lo advierte. El motivo y los estados anteriores quedan en audit_log en la misma transaccion.

Comandos equivalentes (los IDs son ejemplos; confirmar solo tras revisar la evidencia):

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor list-entries
.\.venv\Scripts\python.exe -m brand_threat_monitor authorize-advertiser meta_ad_library ID_ANUNCIANTE --client-id cliente_pichincha --confirm-id ID_ANUNCIANTE --reason "Autorizacion verificada"
.\.venv\Scripts\python.exe -m brand_threat_monitor deactivate-entry meta_ad_library ID_ANUNCIANTE --list whitelist --client-id cliente_pichincha --confirm-id ID_ANUNCIANTE --reason "Autorizacion revocada"
.\.venv\Scripts\python.exe -m brand_threat_monitor resolve-list-conflict meta_ad_library ID_ANUNCIANTE --client-id cliente_pichincha --keep blacklist --confirm-id ID_ANUNCIANTE --reason "Conservar antecedente revisado"
```

Todos admiten --database y --lists-dir. Las modificaciones CLI usan local_operator por defecto y admiten --actor. Las exclusiones administrativas se incluyen en respaldos SQLite/completos. El intercambio masivo CSV/JSON y la restauracion grafica de exclusiones siguen pendientes; los JSON de entrada y SQLite aun no constituyen un unico catalogo importado.


## Intercambio masivo de listas JSON/CSV

Manage lists incluye Import JSON / CSV, Export JSON y Export CSV. Se exportan las entradas activas efectivas (JSON mas SQLite, respetando exclusiones administrativas), sin sobrescribir archivos. La exportacion no incluye casos ni binarios de evidencia. templates/list_bundle.json muestra el contenedor JSON; tambien se admite un documento JSON individual de whitelist, blacklist o brownlist.

La importacion valida el lote completo antes de modificar datos y muestra cuantos agregara y cuantos omitira por identidad/fuente/alcance ya existentes. Solo agrega entradas activas; no elimina por ausencia, no desactiva entradas ni sobrescribe motivos existentes. Detecta duplicados internos y conflictos blanca/negra entre alcances superpuestos. Los conflictos se rechazan: deben resolverse expresamente en administracion antes de reintentar. Brownlist exige anuncio existente; blacklist exige caso Ataque existente del mismo anunciante/fuente y referencias que correspondan a evidencia registrada en ese caso. No convierte referencias externas no verificadas en antecedentes nuevos.

Antes de una importacion con cambios se crea un respaldo SQLite verificado. El lote y su auditoria se aplican en una transaccion; si falla el respaldo o la transaccion no se importan entradas. list_imports guarda huella del documento, archivo de origen, formato, fecha, actor, motivo, conteos y ruta del respaldo. Reimportar el mismo documento ya aplicado no reactiva entradas desactivadas posteriormente. Si no hay adiciones, no se crea respaldo ni evento de importacion.

CLI: validar primero (sin --apply):

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor export-lists --output data/exports/lists.json
.\.venv\Scripts\python.exe -m brand_threat_monitor import-lists ruta/listas.json
.\.venv\Scripts\python.exe -m brand_threat_monitor import-lists ruta/listas.json --apply --confirm-sha HUELLA_DE_LA_VISTA_PREVIA --reason "Lote revisado"
```

CSV usa las columnas schema_version, list_type, source, advertiser_id, ad_id, scope_type, client_id, reason, reviewer, created_at, active, case_id, evidence_refs y escaped_fields. active debe ser true; IDs se leen como cadenas para conservar ceros iniciales. evidence_refs es un array JSON. Los valores de texto que podrian convertirse en formulas se protegen con apostrofo; escaped_fields enumera los campos protegidos para restaurar exactamente el texto al importar. Mantener ese campo al editar con herramientas externas. UTF-8 BOM facilita abrirlo en Excel. No se aceptan hojas Excel ni CSV arbitrarios sin ese esquema.

Limites iniciales: 5 MiB por archivo y 10000 entradas. El respaldo previo es solo de SQLite porque la importacion no modifica JSON de origen ni archivos de evidencia. La vista previa y el archivo deben revisarse antes de confirmar; la huella de CLI evita aplicar un documento diferente. Las operaciones masivas UI son locales y pueden tardar con lotes grandes.


## Carga automatica y espacio en Ad review

La cola persistida en SQLite se carga al iniciar y al entrar en Ad review, ademas de actualizarse al finalizar una busqueda. No se ejecuta una consulta nueva de Meta ni se importan automaticamente JSON arbitrarios de carpetas de diagnostico. Se muestran todos los anuncios pendientes que coinciden con los filtros, con prioridad de blacklist y observaciones mas recientes primero dentro de cada prioridad. Se conserva seleccion/posicion al actualizar.

Si no hay anuncios aceptados pendientes, la vista muestra la ultima corrida guardada y sus errores/diagnostico en la ficha desplazable. Eso distingue una cola vacia de una busqueda fallida o con anuncios fuera del rango. Los registros excluidos por fecha siguen siendo diagnostico y no casos nuevos de auditoria.

Ad review reserva espacio para acciones y pie, con tabla y ficha redimensionables, scroll vertical/horizontal en tabla y scroll vertical en detalle. Los botones se distribuyen en dos filas. Los mensajes extensos se muestran en el detalle, evitando desplazar los controles fuera de la ventana minima de 850x600.


## Toda la informacion en la ficha de analisis

Ad review presenta datos como secciones y campos legibles, sin imprimir el JSON. Incluye identificacion/observaciones del anuncio, contenido completo y campos adicionales de la fuente, evaluacion de cola, casos/evidencia/eventos/reportes y las ejecuciones JSON relacionadas persistidas. Si no hay anuncios en cola, presenta de la misma forma la ultima ejecucion y sus diagnosticos.

All information abre un explorador Section / field y Value: expandir secciones, seleccionar un campo y leer/copiar su valor completo en el panel inferior. Las estructuras anidadas y campos desconocidos de la fuente se conservan; la fila del arbol puede abreviar un valor largo, pero el panel seleccionado no lo trunca. Los campos serializados de contenido/auditoria se decodifican para presentar sus campos, no bloques de JSON.

History muestra corridas y casos con el mismo formato legible. Un valor ausente se muestra como Not available; false, cero, texto vacio y listas vacias se distinguen. El contenido original de anuncios no se traduce ni se modifica y los archivos de resultados mantienen su formato JSON. Visualizar los campos no descarga multimedia ni abre URLs automaticamente.
