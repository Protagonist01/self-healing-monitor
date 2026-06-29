import psycopg2
import sqlite3
import time
from healer.src.config import settings

def is_sqlite_backend() -> bool:
    return settings.audit_backend_name == "sqlite"

def sql_placeholders(count: int) -> str:
    token = "?" if is_sqlite_backend() else "%s"
    return ", ".join([token] * count)

def get_db_connection():
    """
    Establish connection to the configured audit database.
    """
    if is_sqlite_backend():
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    return psycopg2.connect(settings.DATABASE_URL)

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
            print(f"Waiting for database to become available... Retries left: {retries}. Error: {e}")
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
                    decision        TEXT NOT NULL,  -- auto_execute | human_approval | notify_only
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
                    status          TEXT NOT NULL, -- pending | approved | rejected
                    created_at      TIMESTAMPTZ NOT NULL,
                    updated_at      TIMESTAMPTZ,
                    state_snapshot  JSONB NOT NULL -- Full HealerState snapshot at gate time
                );
            """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_queue(status);")
        conn.commit()
        print("Database schema initialized successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error initializing database schema: {e}")
        raise
    finally:
        cur.close()
        if conn:
            conn.close()
