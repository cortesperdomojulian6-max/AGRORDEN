"""Configuración del ETL: variables de entorno y conexión PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

RAW_DIR: Path = Path(os.environ.get("ETL_RAW_DIR", str(REPO_ROOT / "data" / "raw")))


def db_config() -> dict[str, str | int]:
    """Parámetros de conexión leídos exclusivamente del entorno."""
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5433")),
        "dbname": os.environ.get("PGDATABASE", "agrorden"),
        "user": os.environ.get("PGUSER", "agrorden_app"),
        "password": os.environ["PGPASSWORD"],
    }


def get_connection():
    """Abre una conexión psycopg2 a la base agrorden."""
    return psycopg2.connect(**db_config())
