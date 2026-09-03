# AGRORDEN

ERP Ganadero — Spec-Driven Development. Gestión completa de hato: animales, reproducción, producción lechera, pesajes, alertas y más.

## Estructura

```
app/              Dashboard Streamlit (interfaz principal)
db/
  ddl/            Esquema PostgreSQL (001..010)
  seeds/          Catálogos iniciales
docs/             Especificaciones SDD, diccionario de datos y specs técnicos
etl/              Módulos de conexión y transformación (config, extract, transform, load)
scripts/          Utilidades (sincronización, ingesta, gestión de la BD)
tests/            Pruebas unitarias y de aceptación (pytest)
```

## Flujo de ramas

- `main`: estado estable e integrado. Solo entra por merge.
- `front`: desarrollo visual (app/dashboard.py, .streamlit/, estética).
- `backend`: desarrollo de BD, ETL, migraciones y scripts de datos.
- Commits semánticos orientados al dominio: `feat(front): identidad visual`.

## Configuración

1. Copiar `.env.example` a `.env` y completar credenciales de PostgreSQL.
2. Instalar dependencias:
   ```
   python -m pip install -r requirements.txt
   ```
3. Crear la base de datos y ejecutar los DDLs:
   ```
   psql -d agrorden -f db/ddl/001_schema_ganadero.sql
   psql -d agrorden -f db/seeds/002_seed_catalogos.sql
   psql -d agrorden -f db/ddl/003_etl_cuarentena.sql
   ...
   psql -d agrorden -f db/ddl/010_venta_animales.sql
   ```
4. Sincronizar datos desde los Excel fuente:
   ```
   python scripts/sincronizar_2026.py
   ```
5. Arrancar el dashboard:
   ```
   python -m streamlit run app/dashboard.py --server.port 8501
   ```
   O usar el script de inicio rápido:
   ```
   .\start.ps1
   ```
6. Pruebas:
   ```
   python -m pytest tests/ -v
   ```

## Componentes principales

- **Dashboard** (`app/dashboard.py`): interfaz web con navegación por secciones, fichas de animal, gráficas de peso/producción, alertas, formularios de captura.
- **Sincronizador** (`scripts/sincronizar_2026.py`): ETL idempotente que recarga datos desde los 3 archivos Excel fuente.
- **DB**: PostgreSQL con vistas materializadas para indicadores (días abiertos, ganancia de peso, producción, machine de reproducción de 7 pasos).

## Regla de oro

**NADA se comitea ni se hace push sin aprobación explícita del usuario.**
