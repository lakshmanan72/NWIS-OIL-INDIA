import logging
from typing import Generator, Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from .config import db_config

logger = logging.getLogger("nwis.db")

_engine = None
_SessionFactory = None


def get_engine(db_url: Optional[str] = None):
    global _engine, _SessionFactory
    url = db_url or db_config.database_url

    if _engine is not None and (db_url is None or str(_engine.url) == url):
        return _engine

    kwargs: Dict[str, Any] = {"echo": False}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    elif url.startswith("postgresql"):
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    try:
        _engine = create_engine(url, **kwargs)
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        logger.info(f"Database engine initialized for dialect: {_engine.dialect.name}")
    except Exception as e:
        logger.warning(f"Failed to create database engine for {url}: {e}")
        _engine = None
        _SessionFactory = None

    return _engine


def get_session(db_url: Optional[str] = None) -> Optional[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        get_engine(db_url)
    if _SessionFactory is None:
        return None
    return _SessionFactory()


def get_db() -> Generator[Optional[Session], None, None]:
    """FastAPI dependency for obtaining a database session."""
    session = get_session()
    if session is None:
        yield None
        return
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> Dict[str, Any]:
    """Inspects database health and PostGIS availability."""
    engine = get_engine()
    if engine is None:
        return {
            "connected": False,
            "dialect": "none",
            "postgis_active": False,
            "error": "Engine not initialized",
        }

    try:
        with engine.connect() as conn:
            # Check basic connectivity
            conn.execute(text("SELECT 1"))
            dialect = engine.dialect.name

            # Check PostGIS
            postgis_active = False
            postgis_version = None
            if dialect == "postgresql":
                try:
                    res = conn.execute(text("SELECT PostGIS_Version();")).scalar()
                    postgis_active = True
                    postgis_version = str(res)
                except Exception:
                    postgis_active = False

            return {
                "connected": True,
                "dialect": dialect,
                "postgis_active": postgis_active,
                "postgis_version": postgis_version,
            }
    except Exception as e:
        return {
            "connected": False,
            "dialect": engine.dialect.name if engine else "unknown",
            "postgis_active": False,
            "error": str(e),
        }
