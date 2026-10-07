import psycopg2
import sqlite3
import time
from threading import Lock
from typing import Optional

try:
    from psycopg2 import pool as pg_pool
except ImportError:
    pg_pool = None

from healer.src.config import settings


_pool: Optional["pg_pool.SimpleConnectionPool"] = None
_pool_lock = Lock()
_sqlite_lock = Lock()


def _init_pg_pool():
    """Initialize the PostgreSQL connection pool (lazy, thread-safe)."""
    global _pool
    if _pool is not None:
        return _pool
    if pg_pool is None:
        return None
    with _pool_lock:
        if _pool is None:
            try:
                _pool = pg_pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=settings.DATABASE_URL,
                    **(
                        {"password": settings.POSTGRES_PASSWORD}
                        if settings.POSTGRES_PASSWORD
                        else {}
                    ),
                )
                print("PostgreSQL connection pool initialized (1-10 connections).")
            except Exception as e:
                print(f"Could not create connection pool, falling back to direct connections: {e}")
                _pool = None
    return _pool


class PooledConnection:
    """
    Context manager that returns a pooled PG connection or a plain SQLite connection.
    Automatically returns the connection to the pool on exit.
    """

    def __init__(self):
        self.conn = None
        self._from_pool = False

    def __enter__(self):
        if is_sqlite_backend():
            self.conn = sqlite3.connect(settings.SQLITE_PATH)
            self.conn.row_factory = sqlite3.Row
            return self.conn
        p = _init_pg_pool()
        if p is not None:
            self.conn = p.getconn()
            self._from_pool = True
        else:
            self.conn = psycopg2.connect(
                settings.DATABASE_URL,
                **({"password": settings.POSTGRES_PASSWORD} if settings.POSTGRES_PASSWORD else {}),
            )
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is None:
            return
        if exc_type is not None:
            self.conn.rollback()
        if self._from_pool and _pool is not None:
            _pool.putconn(self.conn)
        else:
            self.conn.close()
        self.conn = None


def is_sqlite_backend() -> bool:
    return settings.audit_backend_name == "sqlite"


def sql_placeholders(count: int) -> str:
    token = "?" if is_sqlite_backend() else "%s"
    return ", ".join([token] * count)


def get_db_connection():
    """
    Establish connection to the configured audit database.
    For PostgreSQL, uses the connection pool if available.
    For SQLite, uses a thread-safe direct connection.
    """
    if is_sqlite_backend():
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    p = _init_pg_pool()
    if p is not None:
        return p.getconn()
    return psycopg2.connect(
        settings.DATABASE_URL,
        **({"password": settings.POSTGRES_PASSWORD} if settings.POSTGRES_PASSWORD else {}),
    )


def return_db_connection(conn):
    """Return a connection to the pool or close it if not pooled."""
    if is_sqlite_backend():
        conn.close()
        return
    if _pool is not None:
        _pool.putconn(conn)
    else:
        conn.close()


def close_pg_pool():
    """Close all connections in the pool. Call on application shutdown."""
    global _pool
    if _pool is not None:
        with _pool_lock:
            if _pool is not None:
                _pool.closeall()
                _pool = None
                print("PostgreSQL connection pool closed.")


def init_db():
    """
    Initialize database schema (create tables & indexes if they don't exist).
    Retries in case database is booting up.
    """
    conn = None
    retries = 5
    while retries > 0:
        try:
            conn = get_db_connection()
            break
        except Exception as e:
            print(
                f"Waiting for database to become available... Retries left: {retries}. Error: {e}"
            )
            retries -= 1
            time.sleep(3)

    if not conn:
        raise Exception("Could not connect to database after several retries.")

    cur = conn.cursor()
    try:
        if is_sqlite_backend():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id              TEXT PRIMARY KEY,
                    incident_id     TEXT NOT NULL,
                    service         TEXT NOT NULL,
                    alert_name      TEXT NOT NULL,
                    decision        TEXT NOT NULL,
                    confidence      REAL,
                    selected_action TEXT,
                    alert_resolved  INTEGER,
                    received_at     TEXT NOT NULL,
                    completed_at    TEXT,
                    record          TEXT NOT NULL
                );
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id              UUID PRIMARY KEY,
                    incident_id     UUID NOT NULL,
                    service         TEXT NOT NULL,
                    alert_name      TEXT NOT NULL,
                    decision        TEXT NOT NULL,
                    confidence      FLOAT,
                    selected_action TEXT,
                    alert_resolved  BOOLEAN,
                    received_at     TIMESTAMPTZ NOT NULL,
                    completed_at    TIMESTAMPTZ,
                    record          JSONB NOT NULL
                );
            """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_service ON audit_log(service);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_received ON audit_log(received_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_log(decision);")

        if is_sqlite_backend():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS approval_queue (
                    id              TEXT PRIMARY KEY,
                    incident_id     TEXT NOT NULL,
                    service         TEXT NOT NULL,
                    alert_name      TEXT NOT NULL,
                    action          TEXT NOT NULL,
                    confidence      REAL NOT NULL,
                    reasoning       TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT,
                    state_snapshot  TEXT NOT NULL
                );
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS approval_queue (
                    id              UUID PRIMARY KEY,
                    incident_id     UUID NOT NULL,
                    service         TEXT NOT NULL,
                    alert_name      TEXT NOT NULL,
                    action          TEXT NOT NULL,
                    confidence      FLOAT NOT NULL,
                    reasoning       TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    created_at      TIMESTAMPTZ NOT NULL,
                    updated_at      TIMESTAMPTZ,
                    state_snapshot  JSONB NOT NULL
                );
            """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_queue(status);")

        if is_sqlite_backend():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS incident_queue (
                    id              TEXT PRIMARY KEY,
                    incident_id     TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    state_snapshot  TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    started_at      TEXT,
                    completed_at     TEXT,
                    error           TEXT
                );
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS incident_queue (
                    id              UUID PRIMARY KEY,
                    incident_id     UUID NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    state_snapshot  JSONB NOT NULL,
                    created_at      TIMESTAMPTZ NOT NULL,
                    started_at      TIMESTAMPTZ,
                    completed_at    TIMESTAMPTZ,
                    error           TEXT
                );
            """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON incident_queue(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_incident ON incident_queue(incident_id);")

        if is_sqlite_backend():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS incident_outcomes (
                    id              TEXT PRIMARY KEY,
                    incident_id     TEXT NOT NULL,
                    action_taken    TEXT NOT NULL,
                    alert_resolved  INTEGER NOT NULL,
                    verified        INTEGER NOT NULL DEFAULT 0,
                    root_cause      TEXT,
                    feedback_label  TEXT,
                    notes           TEXT,
                    created_at      TEXT NOT NULL
                );
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS incident_outcomes (
                    id              UUID PRIMARY KEY,
                    incident_id     UUID NOT NULL,
                    action_taken    TEXT NOT NULL,
                    alert_resolved  BOOLEAN NOT NULL,
                    verified        BOOLEAN NOT NULL DEFAULT FALSE,
                    root_cause      TEXT,
                    feedback_label  TEXT,
                    notes           TEXT,
                    created_at      TIMESTAMPTZ NOT NULL
                );
            """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_outcomes_incident ON incident_outcomes(incident_id);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_outcomes_action ON incident_outcomes(action_taken);"
        )

        conn.commit()
        print("Database schema initialized successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error initializing database schema: {e}")
        raise
    finally:
        cur.close()
        return_db_connection(conn)
