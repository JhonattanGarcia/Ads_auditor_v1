# Perfiles y manifiesto

example.json contiene un perfil ficticio. searches.json selecciona perfiles por ruta y habilitacion. El cargador config/profiles.py valida schema_version=1.0, identidad del cliente, pais ISO alfa-2, criterios, booleanos, zona horaria, plantilla y rango temporal. Cada criterio habilitado genera una consulta independiente. Todas las configuraciones seleccionadas se validan antes de iniciar la primera consulta.

Las rutas de perfiles y output.directory se resuelven respecto al manifiesto. Entradas desactivadas no requieren que el archivo exista. Los perfiles habilitados por el manifiesto se validan incluso si el perfil esta desactivado; este ultimo no genera consultas. No se admiten claves JSON, rutas ni client_id duplicados. Perfiles reales deben guardarse en profiles/local/, excluido de Git.

Comprobar sin consultar ni crear carpetas:

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor validate-profiles profiles/searches.json
.\.venv\Scripts\python.exe ejecutar_busqueda.py --manifest profiles/searches.json --dry-run
```

Ejecutar todos los criterios habilitados:

```powershell
.\.venv\Scripts\python.exe ejecutar_busqueda.py --manifest profiles/searches.json --max-scan 30
```

Cada consulta genera un run_id y results.json propio, con client_id y client_name. El formato actual es una corrida por criterio; aun no existe una corrida agregada de todo el manifiesto. La carpeta de salida se comprueba mediante escritura temporal antes de consultar. --output solo admite una consulta para evitar sobrescribir resultados de varios criterios. --profile sigue disponible y es mutuamente excluyente con --manifest.

Los errores del conector se guardan por consulta y permiten continuar con las restantes; una cancelacion detiene el lote. La validacion de pais ISO no garantiza que Meta soporte ese pais. La edicion de perfiles desde UI y la configuracion de todas las rutas se incorporaran mas adelante.
