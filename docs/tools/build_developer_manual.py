"""Generate the developer PDF from code and an isolated temporary database.

Documentation dependencies: reportlab, pypdf. Run from the project root.
"""
import ast,hashlib,json,subprocess,tempfile
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate,Frame,PageTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing,Rect,String,Line

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'docs/Ad_monitor_Manual_del_desarrollador.pdf'
DATE='23 de noviembre de 2026'
INK=colors.HexColor('#202A30');TEAL=colors.HexColor('#29444A');IVORY=colors.HexColor('#F6F3ED');CAMEL=colors.HexColor('#C49A67')
WIDTH=A4[0]-36*mm


def inventory():
    """Extract all product methods, including nested callbacks, without importing the UI."""
    records=[]
    paths=sorted((ROOT/'src/brand_threat_monitor').rglob('*.py'))+[ROOT/'ejecutar_busqueda.py',ROOT/'iniciar_interfaz.py']
    for path in paths:
        source=path.read_text(encoding='utf-8-sig');tree=ast.parse(source);methods=[]
        def visit(node,prefix=''):
            """Traverse classes and nested definitions while retaining qualified names."""
            for child in ast.iter_child_nodes(node):
                if isinstance(child,ast.ClassDef):visit(child,prefix+child.name+'.')
                elif isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    methods.append({'name':prefix+child.name,'args':ast.unparse(child.args),'line':child.lineno,
                        'doc':ast.get_docstring(child) or 'Sin docstring.','decorators':[ast.unparse(d) for d in child.decorator_list],
                        'returns':ast.unparse(child.returns) if child.returns else ''})
                    visit(child,prefix+child.name+'.')
                else:visit(child,prefix)
        visit(tree)
        records.append({'path':path.relative_to(ROOT).as_posix(),'methods':methods,'doc':ast.get_docstring(tree) or '',
            'hash':hashlib.sha256(source.encode()).hexdigest()})
    return records


class ManualDoc(BaseDocTemplate):
    """Provide outline bookmarks and a linked table of contents."""
    def afterFlowable(self,flowable):
        """Register major headings and module subsections in the PDF navigation tree."""
        if isinstance(flowable,Paragraph) and flowable.style.name in ('H1','H2'):
            level=0 if flowable.style.name=='H1' else 1;text=flowable.getPlainText()
            if self.page==1 or text=='Contenido': return
            key='h'+hashlib.sha1((str(level)+text).encode()).hexdigest()
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(text,key,level,False)
            if level==0: self.notify('TOCEntry',(level,text,self.page,key))


def furniture(canvas,doc):
    """Draw running page furniture outside the body frame."""
    canvas.saveState()
    if doc.page>1:
        canvas.setFillColor(TEAL);canvas.rect(0,A4[1]-14*mm,A4[0],14*mm,fill=1,stroke=0)
        canvas.setFont('Body',8);canvas.setFillColor(IVORY)
        canvas.drawString(18*mm,A4[1]-9*mm,'AD MONITOR / MANUAL DEL DESARROLLADOR')
    canvas.setStrokeColor(CAMEL);canvas.line(18*mm,15*mm,A4[0]-18*mm,15*mm)
    canvas.setFont('Body',8);canvas.setFillColor(TEAL)
    canvas.drawString(18*mm,10*mm,'Edición técnica / '+DATE)
    canvas.drawRightString(A4[0]-18*mm,10*mm,str(doc.page));canvas.restoreState()


def register_fonts():
    """Embed local fonts with Spanish glyph support; no remote font download."""
    folder=Path('C:/Windows/Fonts')
    if (folder/'segoeui.ttf').exists():pairs=[('Body','segoeui.ttf'),('BodyBold','segoeuib.ttf'),('Mono','consola.ttf')]
    else:
        folder=Path('/usr/share/fonts/truetype/dejavu');pairs=[('Body','DejaVuSans.ttf'),('BodyBold','DejaVuSans-Bold.ttf'),('Mono','DejaVuSansMono.ttf')]
    for name,file in pairs:pdfmetrics.registerFont(TTFont(name,str(folder/file)))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='Body',boldItalic='BodyBold')


MODULES=[
('backups','Instantáneas SQLite, manifiestos, verificación y restauración en destinos nuevos.'),
('collectors','Contrato de fuente, adaptador Meta, fixture y supervisión de proceso.'),
('config','Carga estricta de perfiles, operador CLI, rutas y presupuestos.'),
('domain','Espacio reservado; su existencia no implica una capa de dominio completa.'),
('evidence','Validación y copia administrada de imágenes locales de evidencia.'),
('exports','Expedientes JSON/CSV con protección frente a fórmulas.'),
('history','Filtros por contexto y consultas históricas sin mutaciones.'),
('ingestion','Coordinación de captura, normalización, postfiltrado y persistencia.'),
('lists','Precedencia, administración e intercambio de listas.'),
('review','Cola, decisiones humanas, correcciones y reportes registrados.'),
('search','Adaptación de URL y postfiltrado por inicio del anuncio.'),
('storage','SQLite, migraciones y repositorios idempotentes.'),
('ui','Widgets Tkinter, tema, tarjetas, imágenes y vistas auxiliares.')]

NARRATIVE=[]
NARRATIVE.extend([
('1. Propósito y alcance',[
('Producto','Ad monitor es una aplicación local para recolectar anuncios de Meta, filtrar su inicio por fechas locales y apoyar revisión humana de posibles suplantaciones. Conserva observaciones, listas, evidencia, decisiones e históricos. No es un servicio web ni una operación distribuida.'),
('Identidad técnica','El título gráfico es Ad monitor; el paquete sigue siendo brand_threat_monitor, la distribución brand-threat-monitor y la versión declarada 0.1.0. Cambiar el nombre visible no cambia imports ni rutas.'),
('Referencia','Este manual describe el workspace actual, incluidos docstrings locales. El commit base no acredita que todos los cambios ya estén publicados. Las firmas y líneas del catálogo se extraen del código; pueden cambiar después de editar.'),
('Límites reales','Los resultados son parciales y no equivalentes necesariamente a Biblioteca manual. No confirma fraude ni presenta denuncias automáticas. No autentica analistas, no incorpora reputación externa y no reproduce video. Los reportes son registros de acciones manuales, no consultas de estado a Meta.')]),
('2. Entorno y puntos de entrada',[
('Requisitos','Python 3.11 o superior, Tkinter/Tcl y conectividad para la recolección e imágenes. SQLite, threading, multiprocessing y urllib son biblioteca estándar. La apariencia nativa DWM es específica de Windows; otras plataformas conservan controles del sistema.'),
('Dependencias','pyproject.toml declara meta-ads-collector==1.7.2, tzdata>=2025.2 y Pillow>=12.1,<14. Setuptools>=77 construye el paquete e incluye storage/migrations/*.sql. No hay bloqueo transitivo completo: fijarlo antes de exigir reproducibilidad exacta de versiones.'),
('Entradas','iniciar_interfaz.py delega en ui.app.main; ejecutar_busqueda.py consulta y persiste resultados; python -m brand_threat_monitor llama cli.main para administración. Los scripts instalables son brand-threat-monitor y brand-threat-monitor-ui.'),
('Workspace','Ejecutar desde la raíz para usar rutas locales esperadas; la interfaz admite --workspace PATH. No requiere XAMPP ni el sitio de donde provino el CSS. El perfil público contiene Sample; los registros de uso se guardan fuera de Git.'),
('Documentación','El generador de este PDF usa ReportLab y pypdf como herramientas de documentación, no dependencias de ejecución. Lee AST y migraciones; crea una base temporal aislada, sin abrir la base de uso ni consultar Meta.')]),
('3. Estructura y arquitectura',[
('Capas','UI/CLI invocan servicios; ingestion coordina captura y persistencia; collectors encapsula el proveedor; storage administra SQLite. Listas y revisión humana son servicios separados. Widgets no deben convertirse en la fuente de verdad de decisiones.'),
('Carpetas reservadas','Algunos módulos solo tienen inicializadores o descripciones de reserva. Su presencia no implica una función implementada. Consultar el catálogo de métodos para distinguir capacidades reales.'),
('Acoplamientos','ui.app concentra composición de widgets y coordinación. collectors.meta envuelve client.search_ads del proveedor; date_filter conserva un hook experimental sobre payload. Estos puntos requieren regresiones al actualizar dependencias.'),
('Regla de cambios','Modificar reglas humanas en review/lists; normalización en ingestion; contratos de red en collectors; presentación en ui. Un cambio visual no debe alterar identidad, fecha guardada ni trazabilidad.')]),
('4. Configuración y presupuestos',[
('Perfiles','Un perfil tiene schema_version, client_id, client_name, country, timezone, enabled, days_to_review, criteria y search. approved_advertiser_ids/approved_domains no deben confundirse con las listas efectivas.'),
('Validación','read_json rechaza claves duplicadas. validate_profile trabaja sobre copia y valida ISO de país, campos, criterios y coherencia temporal. load_manifest resuelve rutas relativas al archivo. SearchPlan.queries produce perfiles independientes por criterio habilitado.'),
('Estado de UI','data/search_list.json guarda type=editable_search_list, schema_version=1.0, profiles, output_directory, days_to_review, collection_limits y repeat. SearchRows mantiene identificadores internos de fila. Restaurar evita guardados intermedios.'),
('Límites','UI: 100 anuncios, 20 páginas, 120 s totales y 45 s sin recibir anuncio. CLI de búsquedas mantiene 30 anuncios por defecto. Rangos: anuncios 1–100000; páginas 1–10000; total 1–86400 s; inactividad 1–3600 s. Se aplican por consulta, no al lote completo.'),
('Significado','Max ads cuenta recibidos antes del filtro; Max pages cuenta páginas obtenidas correctamente, incluso vacías. Vacías no reinician inactividad. El primer presupuesto aplicable detiene. Configuraciones guardadas prevalecen sobre defaults nuevos.'),
('Fechas','Days to review=1 es hoy en America/Bogota; N incluye hoy y N-1 días anteriores. Se compara la fecha local de inicio con extremos inclusivos. Mostrar UTC en UI no cambia el filtro. From/To de históricos usan observación o inicio de corrida según vista.')]),
('5. Recolección y postfiltrado',[
('URL','query_builder.prepare valida una URL HTTPS de Facebook ads/library y adapta criterio, país y fechas al perfil. Devuelve URL original, efectiva, parámetros, zona y límites. La efectiva describe lo solicitado, no demuestra que se ejecutara literalmente.'),
('Petición actual','collect elimina start_date[min]/[max] de source_search_url y solicita por criterio/país. MetaCollector usa los defaults activos del proveedor. No se transmiten automáticamente todos los parámetros arbitrarios de la URL al cliente: distinguir filtros de referencia de los ejecutados.'),
('Captura','CollectedAd.to_dict devuelve copia profunda. ingestion normaliza source, ad_id, advertiser_id, delivery_start_time y library_url, y añade observed_at. received_ads conserva cada contenido. Hallar un anuncio antiguo no detiene el flujo.'),
('Postfiltro','post_filter valida fuente/ID y timestamp aware, convierte al huso del perfil, filtra fechas, deduplica por (source, ad_id), ordena inicio descendente y usa desempate estable. Devuelve ads, observations, invalid_records, diagnósticos y reglas/conteos.'),
('Mutación en memoria','Aunque no realiza E/S, post_filter añade date_evaluation a los registros recibidos. No es una función inmutable. Los aceptados son copias; la captura conserva también excluidos, inválidos y duplicados.'),
('Estado de fin','stop_reason distingue collector_finished, scan_limit_reached, page_limit_reached, time_limit_reached, cancelled y source_error. Una captura normal acotada se declara partial; errores sin captura pueden producir failed/unknown. Cero coincidencias no prueba ausencia de anuncios.'),
('Contrato JSON','results.json incluye run_id, source/version, fechas, timezone, date_range, URLs, received_ads, ads, observations, post_filter, errores, warnings, search_limits y connector_stats. filter_mode=post y temporal_filter_status=post_filtered_locally identifican el algoritmo.'),
('Persistencia','persist_result escribe results.json antes de SQLite, crea resumen pending, importa e informa saved/failed. Mantener intacto el documento para recuperación. No existe una transacción única entre JSON, resumen y SQLite.')]),
('6. Concurrencia y repetición',[
('Hilos','El hilo principal es dueño de widgets Tk. Application.worker secuencia consultas en un hilo y publica eventos por queue.Queue. poll ejecuta after cada 150 ms para log, progress, error y done. Cada hilo debe abrir su conexión SQLite.'),
('Proceso','BoundedMetaCollector usa multiprocessing spawn y Pipe unidireccional. El hijo instancia MetaCollector y envía ad, page, request, done o error. El supervisor usa reloj monotónico, comprueba pipe cada 0.1 s y preserva resultados emitidos antes de un fallo.'),
('Limpieza','cleanup termina/join el hijo y usa kill si hace falta; cierra proceso y pipe. El cierre puede sumar margen sobre el plazo configurado. Los targets deben ser importables; mantener guardas __main__ en Windows.'),
('Cancelación','Stop activa Event y desactiva repetición. Se postfiltra y persiste la captura disponible. Cerrar estando busy solicita esperar al guardado; después se cierra nuevamente. Un cierre forzado antes del guardado final puede perder resultados en memoria.'),
('Planificador','repeat contiene enabled y hours; acepta valores finitos de 1 a 8760 horas. Default: off/24 h. Activar programa el primer plazo desde ahora; Run searches inicia inmediatamente. El siguiente intervalo se cuenta tras finalizar el lote, no desde su comienzo.'),
('No solapamiento','busy impide repeticiones simultáneas. Al repetirse se toman búsquedas y límites actuales. Si el arranque automático falla sin entrar en busy, se desactiva para evitar un bucle de errores. Cambios de frecuencia durante ejecución se aplican después.'),
('Cierre y reapertura','Solo se repite con la app abierta. Al restaurar enabled=true se arma un intervalo nuevo. No hay servicio del sistema, tareas cron, recuperación de vencimientos ni ejecución después de cerrar.')]),
('7. Conexiones externas',[
('Meta','El cliente instalado meta-ads-collector 1.7.2 usa https://www.facebook.com/ para contexto/sesión, https://www.facebook.com/ads/library/ y POST a https://www.facebook.com/api/graphql/. Son detalles inspeccionados de la dependencia provisional: no una API pública estable ni Meta Marketing API con token definido por el proyecto.'),
('Sesión y secretos','La dependencia gestiona sesión HTTP, contexto y reintentos. No hay credenciales solicitadas por UI ni secreto Meta declarado en pyproject. No registrar cookies, tokens ni datos de sesión al instrumentar. Cambios o restricciones de Meta pueden romper el adaptador.'),
('Páginas','MetaCollector envuelve client.search_ads y retira el cursor al llegar al presupuesto sin pedir otra página; restaura el método en finally. page_callback envía conteos al padre para conservarlos si luego se cancela/agota el tiempo. Páginas correctas no equivalen a intentos HTTP.'),
('Hook de fechas','date_filter.install_date_filter modifica _build_graphql_payload en el experimento histórico; el flujo normal no lo usa. El adaptador declara capacidad temporal, pero el servidor probado no respetó el intervalo: no tratar ese flag como garantía.'),
('Imágenes web','remote_image usa urllib.request.urlopen con User-Agent y Accept de imagen. Timeout 8 s por apertura; 8 MiB máximos; 20 millones de píxeles y dimensión máxima 12000. PNG/JPEG/WebP/GIF; miniatura hasta 420×300. Acepta HTTP/HTTPS con host y sin credenciales y verifica esquema tras redirección.'),
('Frontera de confianza','No existe allowlist de hosts ni filtro de IP privadas para esas imágenes. Mostrar una tarjeta puede contactar un host del payload. El timeout de urllib no es supervisor de duración total de transferencia. No presentar el preview como sandbox ni como evidencia guardada.'),
('Enlaces','webbrowser.open solo se llama por clic en foto/perfil, anuncio/Biblioteca o destino externo. external_links revisa campos y texto de todas las creatividades, deduplica y desenvuelve l.facebook.com/lm.facebook.com; excluye hosts de Facebook, Instagram y Messenger. No visita destinos para medir reputación.'),
('Sistema','Las fuentes se detectan localmente con fallback; no se descargan Google Fonts. ctypes llama DWM de Windows para el marco. Estas conexiones al sistema no requieren un servicio web ni el archivo CSS original.')]),
('8. SQLite e integridad',[
('Conexiones','connect crea carpeta, usa sqlite3.Row, foreign_keys=ON, journal_mode=WAL y busy_timeout=10000. Cierra al salir; no asumir que el contexto confirma cualquier operación arbitraria del llamador.'),
('Migraciones','initialize aplica SQL ordenado con BEGIN IMMEDIATE y schema_migrations. Una excepción revierte su migración. Hay cinco migraciones en esta edición. Agregar otra numerada: no editar una ya aplicada.'),
('Identidad','ads y advertisers usan claves compuestas con source. Observaciones enlazan anuncios/corridas/consultas/clientes. El repositorio conserva primera y última observación y el payload de observación más reciente, distinto de la fecha de publicación.'),
('Idempotencia','import_result valida versión, actor, identidades y timestamps aware y usa una transacción. Reimportar run_id idéntico y mismo JSON canónico no duplica datos ni audit. Si el contenido cambia con igual ID, se rechaza. No corregir corridas editando JSON importado.'),
('Auditoría','audit_log conserva operación, actor, entidad, before/after y motivo. Triggers rechazan UPDATE/DELETE. No es una firma criptográfica ni protección frente al propietario del archivo. local_operator identifica atribución, no autenticación.'),
('Limpieza de cola','queue_clears usa source/ad_id/client_id y cleared_through. Oculta observaciones hasta la marca, no borra anuncios ni asigna categoría. Una observación posterior reaparece. El contexto sin cliente se codifica como cadena vacía en esta tabla.')])
])
NARRATIVE.extend([
('9. Listas y decisiones humanas',[
('Identificación','Whitelist/blacklist usan advertiser_id; brownlist usa ad_id. Cada entrada tiene actividad, fuente y alcance global o cliente. Los archivos públicos lists/*.json son versionados; no guardar información privada allí por accidente.'),
('Combinación','merge_database_lists une JSON y decisiones activas SQLite y aplica list_exclusions sin reescribir el origen. La huella SHA-256 describe la combinación usada; blacklist exige antecedentes y referencias.'),
('Precedencia','Blanca+negra producen list_conflict. Sin conflicto: negra → known_black/prioridad 1; blanca → known_white/sin cola; marrón → discarded_brown/sin cola; desconocido → pending_review/prioridad 3. Se cruzan identidades y alcances, no nombres parecidos.'),
('Decisiones','open_case reutiliza caso por fuente/anuncio/cliente. decide admite spam, attack y pending. Spam crea brownlist en alcance del caso; Flag usa attack, requiere publisher conocido y evidencia local de hasta 20 MiB y añade blacklist global; Pending registra pending_evidence sin listas.'),
('UI y contrato','Clasificar no muestra confirmación ni pide motivo: la UI pasa un motivo estándar y confirm_id internamente. El servicio sigue comprobando ID exacto; review-case de CLI exige motivo y admite --confirm-id. No suprimir esas validaciones al editar botones.'),
('Evidencia de flag','Flag guarda referencia/hash de tipo local_file: no copia automáticamente el archivo. attach_image es distinto y crea copia administrada local_image. Un preview remoto no satisface por sí solo la evidencia.'),
('Corrección','reopen_case exige ID y motivo, revierte efectos propios y conserva eventos/evidencia y antecedentes sostenidos por otros casos. Clear unreviewed omite conflictos/decisiones previas, revalida dentro de transacción y audita sin clasificar.'),
('Reportes/listas','record_report guarda sent, awaiting_response, action_confirmed o unknown con fecha aware y metadatos. No comunica con Meta. La importación masiva valida antecedentes/conflictos, crea respaldo y conserva procedencia y hash para reimportación idempotente.')]),
('10. Interfaz e imágenes',[
('Pantallas','Application organiza Search setup y Ad review sin encabezados internos. La barra nativa se titula Ad monitor y usa icono transparente. Auditor incluye selección, All information, UTC, filtros e icono de libro para históricos; no hay buscador Client ID.'),
('Carga manual','La carga autom?tica de Ad review lee SQLite. Load results JSON permite seleccionar un results.json copiado, validarlo e importarlo de forma idempotente sin consultar Meta. Limpia filtros visuales, selecciona un anuncio revisable y conserva decisiones/exclusiones anteriores. No acepta run_summary.json ni listas de b?squeda. Si no hay anuncios revisables, expone los diagn?sticos en All information sin mantener una selecci?n anterior.'),
('Botones','Primera fila: Spam, Pending, Flag. Segunda: Previous, Open in Meta, Next. Local evidence está oculto como botón principal, pero existe servicio y ventana desde históricos. La clasificación usa los mismos servicios que CLI.'),
('Tarjeta','AdCard mantiene columnas 1:1:2: anunciante 25%, anuncio 25%, texto/metadatos 50%. Solo el tercer panel se desplaza; imágenes se ajustan conservando proporción. Las fotos abren perfil/Biblioteca mediante clic; destinos externos tienen sección propia.'),
('PhotoImage','Tk necesita un objeto PhotoImage del intérprete correcto con referencia Python viva. clear_images desacopla el image del widget antes de liberar su propietario; invertir orden causa pyimageN does not exist. El reemplazo se configura antes de liberar la imagen anterior.'),
('Workers de imagen','Cada render incrementa image_generation; hilos daemon descargan y encolan datos, poll_images aplica solo generación vigente en hilo Tk. OrderedDict limita caché a 20 entradas. Cambiar/cerrar invalida respuestas viejas sin interrumpir instantáneamente toda petición HTTP existente.'),
('Tema','ui.theme centraliza INK #202A30, PETROLEUM #14252D, TEAL #29444A, IVORY #F6F3ED y CAMEL #C49A67. Fondo general petroleum; pestañas teal/activa ink; botones ink/marfil salvo Spam camel, Pending advertencia y Flag rojo. Scrollbars planas sin flechas.'),
('Portabilidad','Manrope, Inter e IBM Plex Mono se buscan localmente con alternativas. Tkinter no lee CSS: sus tokens se traducen a ttk y widgets Tk. DWM se aplica con ctypes solo en Windows y conserva los controles nativos.')]),
('11. Evidencia, exportación y respaldo',[
('Evidencia local','Se rechazan URLs, UNC y enlaces/junctions. Se verifican hasta 20 MiB, 20 millones de píxeles y 12000 por dimensión, formato y hash esperado. attach_image copia a data/evidence con nuevo ID, nota y audit; elimina copia incompleta si falla.'),
('Exportación','build_case_file reúne contenido, observaciones y eventos; export_case produce JSON/CSV largo y evita sobreescritura. CSV protege prefijos interpretables como fórmulas. Referencias a evidencia no equivalen a adjuntar sus bytes: no es un paquete autocontenido.'),
('SQLite','create_backup produce instantánea verificable, hash/manifiesto e integridad. restore_backup exige destino nuevo. Copiar una base viva ignorando WAL no sustituye ese mecanismo.'),
('Workspace','Incluye SQLite, JSON de perfiles/listas, búsquedas y evidencia referenciada interna o externa. No contiene código, .venv, logs, exports ni todos los results.json separados. Ausencia/hash incorrecto de evidencia puede impedir publicar un respaldo.'),
('Restauración','Verifica miembros/hashes, evita traversal y links, usa carpeta nueva y reubica evidencia con auditoría. SQLite tiene instantánea transaccional; no hay transacción global de todos los archivos mientras otros procesos los cambian.')]),
('12. Mantenimiento y extensión',[
('Defaults','Cambiar config/limits.py y revisar defaults explícitos del CLI. No sustituir sin aviso valores guardados. Probar listas antiguas sin collection_limits y campos temporalmente vacíos.'),
('Otro proveedor','Implementar contexto y búsqueda según collectors.base y usar fixtures/collector_factory. ingestion todavía fija source=meta_ad_library y campos Meta: reemplazar solo el adaptador no convierte el motor completo en multifuente.'),
('Actualizar Meta','No parchear .venv como solución permanente. Actualizar pyproject y adaptador, revisar search_ads, modelos, stats y hook _build_graphql_payload. Primero probar sin red; después consulta acotada deliberada.'),
('Cambiar tablas','Agregar migración numerada, probar base nueva y actualización, revisar FKs e índices y actualizar test de migraciones. Respaldar un workspace operativo antes de cambios.'),
('UI','Mantener workers sin Tk, revalidar selección al refrescar, cancelar callbacks al destruir y probar pantalla pequeña/fuentes alternativas. No bloquear el hilo principal con red, sleeps o transacciones largas.'),
('Metadatos nuevos','Conservar payload y representar en card_data/InformationWindow. No confundir ausencia con 0 o False. Probar creatividades múltiples, campos faltantes y tipos inesperados.'),
('Docstrings','Todas las funciones del producto y tests tienen documentación local. El catálogo incluye callbacks privados y firmas completas. Actualizar contrato/documentación junto con lógica: un comentario no reemplaza una prueba.')]),
('13. Pruebas y resolución de problemas',[
('Base verificada','Última ejecución registrada: 154 pruebas aprobadas y arranque --check. No equivale a aceptación funcional integral, cobertura de líneas ni garantía de continuidad del proveedor.'),
('Áreas','Perfiles, URLs, fecha, fixtures, límites, timeouts, cancelación, persistencia, auditoría, listas, correcciones, reportes, exportaciones, backups, imágenes, layout y repetición con reloj simulado. No esperar una hora real para probar el planificador.'),
('Sin coincidencias','Inspeccionar status, coverage, stop_reason, received_ads, post_filter, excluded_by_date, invalid_records y connector_stats. Puede haber captura sin ninguna fecha coincidente o muestras insuficientes por presupuesto.'),
('Fallo SQLite','Conservar results.json intacto y revisar resumen pending/failed. Resolver causa y usar import-results con actor/base correctos. Igual run_id con diferente contenido requiere investigación, no manipular IDs para eludir el control.'),
('Imagen ausente','Revisar URLs, caducidad, límites y formato. Retry limpia caché vigente. Ante pyimageN revisar detach/release, master del intérprete y generación de resultados.'),
('Repetición','Comprobar enabled, hours>=1, app abierta, busy y plazo monotónico. Stop desactiva; reapertura arma intervalo nuevo. Se cuenta desde fin del lote.'),
('Privacidad','No publicar data, evidencia, cookies o secretos en incidencias. Usar Sample/fixtures. Limpiar uso local no elimina ejemplos de documentación ni historial Git; son superficies distintas.')])])


def main():
    """Build narrative, schema dictionary and complete source-method catalog as one PDF."""
    register_fonts()
    styles={
      'Body':ParagraphStyle('BodyTech',fontName='Body',fontSize=9.3,leading=14,spaceAfter=7,textColor=INK,splitLongWords=True),
      'H1':ParagraphStyle('H1',fontName='BodyBold',fontSize=19,leading=24,spaceBefore=8,spaceAfter=14,textColor=TEAL,keepWithNext=True),
      'H2':ParagraphStyle('H2',fontName='BodyBold',fontSize=11,leading=16,spaceBefore=10,spaceAfter=6,textColor=TEAL,keepWithNext=True),
      'Code':ParagraphStyle('Code',fontName='Mono',fontSize=7.4,leading=10.5,spaceAfter=5,textColor=INK,splitLongWords=True),
      'Small':ParagraphStyle('Small',fontName='Body',fontSize=7.6,leading=10.5,spaceAfter=4,textColor=INK,splitLongWords=True),
      'Cell':ParagraphStyle('Cell',fontName='Body',fontSize=8,leading=11,splitLongWords=True)}
    styles['Header']=ParagraphStyle('Header',parent=styles['Cell'],fontName='BodyBold',textColor=IVORY)
    story=[]
    def p(text,style='Body'):
        """Append escaped readable text and preserve explicit line breaks."""
        story.append(Paragraph(escape(str(text)).replace('\n','<br/>'),styles[style]))
    def h(text,level=1):
        """Append a navigable major or minor heading."""
        p(text,'H1' if level==1 else 'H2')
    def table(headers,rows,widths):
        """Append a wrapped table whose header repeats across page breaks."""
        cells=[[Paragraph(escape(str(c)).replace('\n','<br/>'),styles['Header' if i==0 else 'Cell']) for c in row] for i,row in enumerate([headers]+rows)]
        t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,IVORY]),
          ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
          ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),1,CAMEL)]))
        story.append(t);story.append(Spacer(1,8))
    records=inventory();digest=hashlib.sha256(''.join(r['path']+r['hash'] for r in records).encode()).hexdigest()
    revision=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'rev-parse','--short','HEAD'],cwd=ROOT,text=True).strip()
    story.append(Spacer(1,30*mm));h('AD MONITOR');h('Manual del desarrollador')
    p('Arquitectura · Métodos · Datos · Conexiones · Mantenimiento','H2')
    p('Edición: '+DATE);p('Versión 0.1.0 / commit base '+revision)
    p('Basado en el código del workspace. No contiene búsquedas reales, credenciales ni evidencia de usuarios.')
    p(f"Inventario: {len(records)} archivos Python de producto y {sum(len(r['methods']) for r in records)} funciones/métodos, incluidos callbacks.")
    p('Huella fuente: '+digest,'Code')
    story.append(PageBreak());h('Contenido')
    toc=TableOfContents();toc.levelStyles=[ParagraphStyle('TOC0',fontName='BodyBold',fontSize=10,leading=15,spaceBefore=8,textColor=TEAL),ParagraphStyle('TOC1',fontName='Body',fontSize=8,leading=12,leftIndent=12,textColor=INK)]
    story.append(toc)
    for title,sections in NARRATIVE:
        story.append(PageBreak());h(title)
        for subtitle,body in sections:h(subtitle,2);p(body)
        if title.startswith('2.'):
            p('python -m venv .venv\n.venv\\Scripts\\python.exe -m pip install -e .\n.venv\\Scripts\\python.exe iniciar_interfaz.py','Code')
        if title.startswith('3.'):
            table(['Carpeta','Responsabilidad'],[[a+'/',b] for a,b in MODULES],[95,WIDTH-95])
            d=Drawing(WIDTH,140)
            for x,y,label in [(0,95,'UI / CLI'),(172,95,'ingestion / search'),(344,95,'collectors / Meta'),(0,25,'review / lists'),(172,25,'SQLite + JSON'),(344,25,'evidence / exports')]:
                d.add(Rect(x,y,138,33,fillColor=TEAL,strokeColor=None));d.add(String(x+69,y+13,label,textAnchor='middle',fontName='Body',fontSize=8,fillColor=IVORY))
            for coords in [(138,112,172,112),(310,112,344,112),(241,95,241,58),(138,41,172,41),(310,41,344,41)]:d.add(Line(*coords,strokeColor=CAMEL,strokeWidth=2))
            story.append(d)
    story.append(PageBreak());h('14. Comandos y operación')
    p('Ejecutar desde la raíz. Ejemplos de IDs ficticios; las operaciones de escritura requieren actor y algunas exigen motivo/confirmación interna.')
    commands=[('Ayuda','python -m brand_threat_monitor --help'),('Vista previa sin red','python ejecutar_busqueda.py --dry-run --max-scan 100 --max-pages 20'),
      ('Consulta con límites','python ejecutar_busqueda.py --profile profiles/example.json --max-scan 100 --max-pages 20 --max-duration 120 --idle-timeout 45 --actor local_operator'),
      ('Operador CLI','python -m brand_threat_monitor set-operator local_operator'),('Inicializar base','python -m brand_threat_monitor init-db'),
      ('Validar perfiles','python -m brand_threat_monitor validate-profiles profiles/searches.json'),('Reimportar resultado','python -m brand_threat_monitor import-results data/results/SAMPLE_RUN/results.json --actor local_operator'),
      ('Cola','python -m brand_threat_monitor review-queue --country CO --criterion Sample'),('Exportar caso','python -m brand_threat_monitor export-case SAMPLE_CASE --format json --output data/exports/sample_case.json'),
      ('Respaldar workspace','python -m brand_threat_monitor backup-workspace --workspace . --directory data/backups --actor local_operator'),('Restauración','python -m brand_threat_monitor restore-workspace --help'),
      ('Pruebas','python -m unittest discover -s tests/unit -q'),('Arranque sin búsqueda','python iniciar_interfaz.py --check'),
      ('Regenerar este PDF','python -m pip install reportlab pypdf\npython docs/tools/build_developer_manual.py')]
    for title,command in commands:h(title,2);p(command,'Code')
    story.append(PageBreak());h('15. Diccionario SQLite')
    p('Extraído de una base temporal inicializada con las migraciones. PK indica posición en la clave compuesta. Se incluyen relaciones, índices explícitos y nombres de triggers. No usa registros de data/.')
    from brand_threat_monitor.storage.database import connect,initialize
    with tempfile.TemporaryDirectory() as temp:
        with connect(Path(temp)/'schema.sqlite3') as db:
            initialize(db)
            tables=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            for row in tables:
                name=row['name'];h(name,2);cols=db.execute('PRAGMA table_info('+name+')').fetchall()
                table(['Columna','Tipo','Obligatoria','PK','Default'],[[c['name'],c['type'],'Sí' if c['notnull'] or c['pk'] else 'No',c['pk'] or '—',c['dflt_value'] or '—'] for c in cols],[148,52,68,30,WIDTH-298])
                fks=db.execute('PRAGMA foreign_key_list('+name+')').fetchall()
                if fks:p('Relaciones: '+'; '.join(f"{f['from']} → {f['table']}.{f['to']}" for f in fks),'Small')
                for index in db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",(name,)):p(index['sql'],'Code')
                triggers=db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",(name,)).fetchall()
                if triggers:p('Triggers: '+', '.join(t['name'] for t in triggers),'Small')
            p('Migraciones: '+', '.join(r['version'] for r in db.execute('SELECT version FROM schema_migrations ORDER BY version')))
    story.append(PageBreak());h('16. Catálogo de funciones y métodos')
    p('Inventario de código de producto, sin dependencias ni tests. Incluye métodos privados y callbacks anidados. Firmas, parámetros, retornos anotados, decoradores y líneas corresponden al workspace. El docstring se conserva en su idioma original (mayoritariamente inglés) para buscarlo literalmente en el código.')
    for record in records:
        if not record['methods']:continue
        h(record['path'],2)
        if record['doc']:p(record['doc'],'Small')
        for method in record['methods']:
            sig=method['name']+'('+method['args']+')'+(' -> '+method['returns'] if method['returns'] else '')
            location=f"Línea {method['line']}"+(' / '+', '.join('@'+d for d in method['decorators']) if method['decorators'] else '')
            story.append(KeepTogether([Paragraph(escape(sig),styles['Code']),Paragraph(escape(location),styles['Small']),Paragraph(escape(method['doc']).replace('\n','<br/>'),styles['Body'])]))
    story.append(PageBreak());h('17. Inventario y trazabilidad')
    p('Se incluyen inicializadores y reservas sin funciones. La huella abreviada es SHA-256 del texto UTF-8 sin BOM, no de bytes brutos. Regenerar el documento cuando cambien firmas, migraciones o comportamiento.')
    table(['Archivo','Métodos','SHA-256 / prefijo'],[[r['path'],len(r['methods']),r['hash'][:12]] for r in records],[WIDTH-135,55,80])
    h('Referencias internas',2)
    p('Fuentes: pyproject.toml, src/brand_threat_monitor, ejecutar_busqueda.py, iniciar_interfaz.py, migraciones 001–005, perfiles y listas de ejemplo y tests/unit. README resume operación. Las notas históricas en docs pueden describir estados anteriores: prevalecen el código y los contratos verificados de esta edición.')
    p('Huella fuente completa: '+digest,'Code')
    doc=ManualDoc(str(OUTPUT),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=23*mm,bottomMargin=23*mm,
        title='Ad monitor - Manual del desarrollador',author='Ad monitor',subject='Arquitectura, métodos, conexiones y mantenimiento',pageCompression=1)
    doc.addPageTemplates([PageTemplate(id='Manual',frames=[Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=furniture)])
    doc.multiBuild(story)
    from pypdf import PdfReader
    pdf=PdfReader(str(OUTPUT));text='\n'.join(page.extract_text() or '' for page in pdf.pages)
    assert all(key.lower() in text.lower() for key in ['post_filter','BoundedMetaCollector','queue_clears','DWM','source_search_url'])
    assert len(pdf.pages)>=15
    print(json.dumps({'pdf':str(OUTPUT),'pages':len(pdf.pages),'source_files':len(records),'methods':sum(len(r['methods']) for r in records),'bytes':OUTPUT.stat().st_size},ensure_ascii=False))


if __name__=='__main__':main()
