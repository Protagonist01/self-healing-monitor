import json
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from healer.src.audit.db import get_db_connection, is_sqlite_backend, return_db_connection
from healer.src.agent.state import HealerState
from healer.src.agent.graph import healer_app
from healer.src.config import settings

_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_POLL_INTERVAL = 1.0


def _now_iso():
    return (
        datetime.now(timezone.utc).isoformat()
        if is_sqlite_backend()
        else datetime.now(timezone.utc)
    )


def enqueue_incident(state: HealerState) -> Optional[str]:
    """
    Persistently enqueues an incident for processing by the background worker.
    Returns the queue item ID.
    """
    conn = get_db_connection()
    queue_id = str(uuid.uuid4())
    cur = conn.cursor()
    try:
        placeholder = "?" if is_sqlite_backend() else "%s"
        # Serialize intake transactions, including across API threads/processes.
        if is_sqlite_backend():
            cur.execute("BEGIN IMMEDIATE")
        else:
            cur.execute("SELECT pg_advisory_xact_lock(7349201)")
        if settings.DEDUP_WINDOW_SECONDS > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.DEDUP_WINDOW_SECONDS)
            cur.execute(
                f"SELECT state_snapshot FROM incident_queue WHERE created_at >= {placeholder} OR status IN ('pending', 'processing')",
                (cutoff.isoformat() if is_sqlite_backend() else cutoff,),
            )
            for row in cur.fetchall():
                previous = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if all(
                    previous["alert"].get(key) == state["alert"].get(key)
                    for key in ("name", "service")
                ):
                    conn.rollback()
                    return None
        cur.execute(
            f"""
            INSERT INTO incident_queue (id, incident_id, status, state_snapshot, created_at)
            VALUES ({placeholder}, {placeholder}, 'pending', {placeholder}, {placeholder})
            """,
            (queue_id, state["incident_id"], json.dumps(state), _now_iso()),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error enqueueing incident: {e}")
        raise
    finally:
        cur.close()
        return_db_connection(conn)
    return queue_id


def reset_stale_incidents():
    """
    Quarantine interrupted actions: blindly replaying a restart can cause damage.
    Operators must inspect failed queue records and submit a fresh alert if needed.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE incident_queue SET status = 'failed', error = 'Interrupted execution; operator review required' WHERE status = 'processing'"
        )
        reset_count = cur.rowcount
        conn.commit()
        if reset_count:
            print(f"Quarantined {reset_count} interrupted incident(s) for operator review.")
    except Exception as e:
        conn.rollback()
        print(f"Error resetting stale incidents: {e}")
    finally:
        cur.close()
        return_db_connection(conn)


def _claim_next_incident() -> Optional[dict]:
    """
    Atomically claims the next pending incident by marking it 'processing'.
    Returns the incident state and queue id, or None if the queue is empty.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, state_snapshot FROM incident_queue
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return None

        queue_id, state_json = row[0], row[1]
        placeholder = "?" if is_sqlite_backend() else "%s"
        cur.execute(
            f"""
            UPDATE incident_queue SET status = 'processing', started_at = {placeholder}
            WHERE id = {placeholder} AND status = 'pending'
            """,
            (_now_iso(), queue_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return None
        conn.commit()

        state = json.loads(state_json) if isinstance(state_json, str) else state_json
        return {"queue_id": queue_id, "state": state}
    except Exception as e:
        conn.rollback()
        print(f"Error claiming incident from queue: {e}")
        return None
    finally:
        cur.close()
        return_db_connection(conn)


def _complete_incident(queue_id: str, success: bool, error: str = ""):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        status = "completed" if success else "failed"
        placeholder = "?" if is_sqlite_backend() else "%s"
        cur.execute(
            f"""
            UPDATE incident_queue
            SET status = {placeholder}, completed_at = {placeholder}, error = {placeholder}
            WHERE id = {placeholder}
            """,
            (status, _now_iso(), error or None, queue_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error completing incident {queue_id}: {e}")
    finally:
        cur.close()
        return_db_connection(conn)


def _worker_loop():
    """
    Main worker loop. Polls the incident queue and processes incidents sequentially.
    """
    print("Incident queue worker started.")
    while not _stop_event.is_set():
        claimed = _claim_next_incident()
        if claimed:
            queue_id = claimed["queue_id"]
            state: HealerState = claimed["state"]
            print(f"Processing queued incident: {state['incident_id']} (queue: {queue_id})")
            try:
                healer_app.invoke(state)
                _complete_incident(queue_id, success=True)
            except Exception as e:
                print(f"Error processing incident {state['incident_id']}: {e}")
                _complete_incident(queue_id, success=False, error=str(e))
        else:
            _stop_event.wait(_POLL_INTERVAL)
    print("Incident queue worker stopped.")


def start_worker():
    """Starts the background worker thread (idempotent)."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    reset_stale_incidents()
    _worker_thread = threading.Thread(target=_worker_loop, name="incident-worker", daemon=True)
    _worker_thread.start()


def stop_worker():
    """Signals the worker thread to stop and waits for it to finish."""
    global _worker_thread
    _stop_event.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join()
    _worker_thread = None
