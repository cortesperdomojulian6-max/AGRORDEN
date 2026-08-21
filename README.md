# AGRORDEN
PRYOYECTO SOLUCION AGRO

ERP Ganadero — Spec-Driven Development. Ver `docs/system_context.md`, `docs/data_dictionary.md` y `docs/spec_etl_ingesta.md`.

## Estructura
```
docs/    Especificaciones SDD, diccionario de datos y specs técnicos
db/
  ddl/   Esquema PostgreSQL (001_schema_ganadero.sql, 003_etl_cuarentena.sql)
  seeds/ Catálogos iniciales (002_seed_catalogos.sql)
etl/     Módulos de ingesta (config, extract, transform, load)
scripts/ Utilidades (perfilado, ingesta, gestión de la BD local)
tests/   Pruebas unitarias y de aceptación (pytest)
```

## Flujo de ramas
- `main`: estado estable e integrado. Solo entra por merge.
- `backend`: desarrollo de BD, ETL y servicios. Espejo de trabajo diario.
- `frontend`: desarrollo web (se creará al iniciar esa fase).
- Commits semánticos orientados al dominio: `feat: implementa tabla pesajes`.

## Configuración
1. Copiar `.env.example` a `.env` y completar credenciales.
2. Instalar dependencias: `python -m pip install -r requirements.txt`
3. Crear la base de datos y ejecutar:
```
psql -d agrorden -f db/ddl/001_schema_ganadero.sql
psql -d agrorden -f db/seeds/002_seed_catalogos.sql
psql -d agrorden -f db/ddl/003_etl_cuarentena.sql
```
4. Ingesta: `python scripts/run_ingest.py`
5. Pruebas: `python -m pytest tests/ -v`
