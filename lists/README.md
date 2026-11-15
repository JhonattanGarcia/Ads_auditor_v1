# Listas de referencia

Los tres JSON comienzan vacios, sin identidades ficticias ni clasificaciones reales. Son archivos de intercambio iniciales; su lectura, validacion y cruce estan implementados. La sincronizacion con las tablas de listas SQLite sigue pendiente; por ahora los JSON son la configuracion efectiva de listas y cada resultado conserva su evaluacion.

- whitelist.json: anunciantes autorizados, identificados por source y advertiser_id. Alcance recomendado por cliente/contexto.
- blacklist.json: anunciantes con antecedentes documentados, identificados por source y advertiser_id. Alcance global propuesto.
- brownlist.json: anuncios individuales descartados, identificados por source y ad_id. No excluye otros anuncios del anunciante.

Contrato propuesto para cada entrada: source, identificador correspondiente (cadena, nunca numero), scope, reason, reviewer, created_at y active. scope debe identificar de forma explicita si el alcance es global o de cliente y, en este ultimo caso, el client_id. Blacklist requiere adicionalmente case_id y referencias de evidencia verificable. Las fechas deben incluir zona horaria.

Antes de aplicar cambios: validar formato, duplicados y conflictos blanca/negra del mismo anunciante en alcances aplicables. Los conflictos requieren resolucion explicita; no se elimina ninguna entrada silenciosamente. Sin conflictos, prioridad negra antes de blanca antes de marron. Ninguna entrada negra confirma automaticamente fraude en anuncios nuevos.

Estos archivos estan dentro del repositorio y se publicarian al agregarlos a un commit. Mantener datos reales y evidencia en almacenamiento local hasta definir su politica de versionado. La carpeta documentacion original continua excluida de Git.


## Formato de entrada

Ejemplo ficticio de entrada marron (no se incorpora a las listas reales):

```json
{
  "source": "meta_ad_library",
  "ad_id": "ID_DEL_ANUNCIO",
  "scope": {"type": "client", "client_id": "cliente_pichincha"},
  "reason": "Anuncio irrelevante revisado",
  "reviewer": "analista",
  "created_at": "2026-11-15T12:00:00-05:00",
  "active": true
}
```

Blanca y negra usan advertiser_id en lugar de ad_id. Alcance global: {"type":"global"}, sin client_id. Negra exige tambien case_id y evidence_refs (lista no vacia de referencias). El validador comprueba estructura y referencias presentes; aun no comprueba que el expediente o archivo de evidencia exista.

Se rechazan duplicados activos dentro del mismo tipo, fuente, identidad y alcance. Los conflictos blanca/negra se detectan al cruzar cada anuncio, incluso global frente a cliente. Se conservan las entradas sin resolverlas automaticamente. La cola ordinaria contiene antecedentes negros con prioridad 1 y desconocidos con prioridad 3; los empates se ordenan por fuente e ID para ser reproducibles. No se calcula probabilidad de fraude ni se asigna clasificacion humana.

El ejecutor lee estas listas una vez antes de consultar. --lists-dir permite otra carpeta con los tres archivos obligatorios. No se aceptan archivos ausentes como listas vacias. Su huella SHA-256 queda en list_evaluation y en el resumen para identificar la configuracion usada. Los archivos JSON originales de listas no se copian a SQLite: alli se conserva el resultado de la evaluacion dentro del payload de la corrida.

results.json incluye list_evaluation.decisions, queue, conflicts y counts. run_summary.json expone review_queue, list_conflicts y conteos efectivos (categorias exclusivas por precedencia). pending cuenta la cola total, incluidos antecedentes negros. reported sigue null hasta implementar reportes. Los anuncios blancos y marrones se conservan en resultados y observaciones aunque no se incluyan en la cola.
