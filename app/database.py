"""Database engine and session factory.

Configuration is loaded from a YAML file. The default location is
``/etc/mywebapp/config.yaml`` (as required for variant V2=2). The path may be
overridden with the ``APP_CONFIG_PATH`` environment variable, which is useful
for local development and tests.

Expected config format::

    database_url: postgresql://user:password@127.0.0.1:5432/dbname
"""

import os
from pathlib import Path

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DEFAULT_CONFIG_PATH = "/etc/mywebapp/config.yaml"


def _load_database_url() -> str:
    config_path = os.getenv("APP_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    path = Path(config_path)
    if not path.is_file():
        raise RuntimeError(
            f"Configuration file not found at {config_path}. "
            "Create it (see config/config.yaml.example) or set APP_CONFIG_PATH."
        )

    with path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    database_url = config.get("database_url")
    if not database_url:
        raise RuntimeError(f"`database_url` is missing in {config_path}")
    return database_url


DATABASE_URL = _load_database_url()

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()
