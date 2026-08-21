# Inicia la instancia PostgreSQL dedicada de AGRORDEN (puerto 5433)
$base = "$HOME\pgsql-agrorden"
& "$base\pgsql\bin\pg_ctl.exe" -D "$base\data" -l "$base\server.log" -o "-p 5433" -w start
