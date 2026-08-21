"""Paquete ETL del ERP Ganadero AGRORDEN.

Módulos:
    config     Carga de configuración (.env) y conexión PostgreSQL.
    extract    Lectura de Excel fuente con detección de encabezados.
    transform  Limpieza (R1-R5) y resolución de identidad validada con Robin.
    load       Escritura transaccional en PostgreSQL con cuarentena.
"""

from etl.config import get_connection, db_config

__all__ = ["get_connection", "db_config"]
