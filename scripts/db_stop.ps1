# Detiene la instancia PostgreSQL dedicada de AGRORDEN
$base = "$HOME\pgsql-agrorden"
& "$base\pgsql\bin\pg_ctl.exe" -D "$base\data" -m fast -w stop
