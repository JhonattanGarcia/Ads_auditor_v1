# Migraciones

001_initial.sql crea el esquema inicial. schema_migrations registra versiones aplicadas. initialize aplica cada archivo en una transaccion BEGIN IMMEDIATE y activa claves foraneas y WAL en la conexion. Los SQL se incluyen como recursos del paquete.

No modificar una migracion ya aplicada; agregar un archivo numerado nuevo. La tabla audit_log rechaza UPDATE y DELETE para preservar los eventos desde la aplicacion. Esta proteccion no sustituye controles sobre el archivo SQLite.
