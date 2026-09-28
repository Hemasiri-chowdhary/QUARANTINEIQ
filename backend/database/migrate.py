from sqlalchemy import inspect, text

from backend.database.session import engine, Base
from backend.database import models  # noqa: F401 - registers ORM tables


def _add_column_if_missing(conn, table: str, column: str, definition: str) -> None:
    existing = {c["name"] for c in inspect(conn).get_columns(table)}
    if column not in existing:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'))


def prepare_database() -> None:
    Base.metadata.create_all(bind=engine)
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        if inspect(conn).has_table("tests"):
            _add_column_if_missing(conn, "tests", "source", "VARCHAR DEFAULT 'demo'")
            _add_column_if_missing(conn, "tests", "external_key", "VARCHAR")
            conn.execute(text("UPDATE tests SET source='demo' WHERE source IS NULL"))
        if inspect(conn).has_table("ci_runs"):
            for name, definition in [
                ("source", "VARCHAR DEFAULT 'demo'"),
                ("workflow_run_id", "VARCHAR"),
                ("job_id", "VARCHAR"),
                ("workflow_name", "VARCHAR"),
                ("job_name", "VARCHAR"),
                ("log_excerpt", "TEXT"),
                ("html_url", "VARCHAR"),
                ("branch", "VARCHAR"),
                ("run_attempt", "INTEGER DEFAULT 1"),
            ]:
                _add_column_if_missing(conn, "ci_runs", name, definition)
            conn.execute(text("UPDATE ci_runs SET source='demo' WHERE source IS NULL"))
            conn.execute(text("UPDATE ci_runs SET run_attempt=1 WHERE run_attempt IS NULL"))
        if inspect(conn).has_table("commits"):
            for name, definition in [
                ("repository", "VARCHAR"),
                ("url", "VARCHAR"),
                ("source", "VARCHAR DEFAULT 'demo'"),
            ]:
                _add_column_if_missing(conn, "commits", name, definition)
            conn.execute(text("UPDATE commits SET source='demo' WHERE source IS NULL"))
        if inspect(conn).has_table("incidents"):
            _add_column_if_missing(conn, "incidents", "source", "VARCHAR DEFAULT 'demo'")
            conn.execute(text("UPDATE incidents SET source='demo' WHERE source IS NULL"))
        if inspect(conn).has_table("decisions"):
            _add_column_if_missing(conn, "decisions", "challenge_shown", "BOOLEAN DEFAULT 0")
            _add_column_if_missing(conn, "decisions", "challenge_reason", "TEXT")
            conn.execute(text("UPDATE decisions SET challenge_shown=0 WHERE challenge_shown IS NULL"))
