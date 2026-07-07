from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, quote_plus, unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from app.core.config import get_settings
from app.db import Base, SessionLocal, engine
from app.seed import seed_database


def _server_url(database_url: str) -> tuple[str, str | None]:
    url = make_url(database_url)
    database = url.database
    server = url.set(database=None)
    return server.render_as_string(hide_password=False), database


def ensure_database_exists() -> None:
    settings = get_settings()
    database_url = settings.database_url
    if database_url.startswith("sqlite"):
        return

    server_url, database = _server_url(database_url)
    if not database:
        return

    bootstrap_url = os.getenv("MYSQL_ADMIN_URL") or server_url
    bootstrap_engine = create_engine(bootstrap_url, pool_pre_ping=True)
    quoted_database = database.replace("`", "``")
    target = make_url(database_url)
    with bootstrap_engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{quoted_database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        if os.getenv("MYSQL_ADMIN_URL") and target.username:
            username = target.username.replace("'", "''")
            password = (target.password or "").replace("'", "''")
            conn.execute(text(f"CREATE USER IF NOT EXISTS '{username}'@'localhost' IDENTIFIED BY '{password}'"))
            conn.execute(text(f"CREATE USER IF NOT EXISTS '{username}'@'%' IDENTIFIED BY '{password}'"))
            conn.execute(text(f"GRANT ALL PRIVILEGES ON `{quoted_database}`.* TO '{username}'@'localhost'"))
            conn.execute(text(f"GRANT ALL PRIVILEGES ON `{quoted_database}`.* TO '{username}'@'%'"))
            conn.execute(text("FLUSH PRIVILEGES"))
    bootstrap_engine.dispose()


def run_compat_migrations() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "password_updated_at" not in columns:
            dialect = engine.dialect.name
            column_type = "DATETIME" if dialect in {"mysql", "sqlite"} else "TIMESTAMP"
            conn.execute(text(f"ALTER TABLE users ADD COLUMN password_updated_at {column_type} NULL"))
        conn.execute(text("UPDATE users SET password_updated_at = COALESCE(password_updated_at, CURRENT_TIMESTAMP)"))
        if "diagnosis_kb" in table_names:
            diagnosis_columns = {column["name"] for column in inspector.get_columns("diagnosis_kb")}
            if "verification_method" not in diagnosis_columns:
                conn.execute(text("ALTER TABLE diagnosis_kb ADD COLUMN verification_method TEXT NULL"))
        if "channel_audit_logs" in table_names and engine.dialect.name == "mysql":
            for fk in inspector.get_foreign_keys("channel_audit_logs"):
                if "channel_id" in (fk.get("constrained_columns") or []):
                    conn.execute(text(f"ALTER TABLE channel_audit_logs DROP FOREIGN KEY `{fk['name']}`"))
        if "message_channels" in table_names:
            channel_columns = {column["name"] for column in inspector.get_columns("message_channels")}
            for column_name in ("user_rate_limit_per_minute", "qps_limit", "daily_message_limit"):
                if column_name not in channel_columns:
                    conn.execute(text(f"ALTER TABLE message_channels ADD COLUMN {column_name} INTEGER NULL"))
        if "llm_models" in table_names:
            model_columns = {column["name"] for column in inspector.get_columns("llm_models")}
            if "applicable_scenarios" not in model_columns:
                column_type = "JSON" if engine.dialect.name == "mysql" else "TEXT"
                conn.execute(text(f"ALTER TABLE llm_models ADD COLUMN applicable_scenarios {column_type} NULL"))
            if "error_rate" not in model_columns:
                conn.execute(text("ALTER TABLE llm_models ADD COLUMN error_rate FLOAT DEFAULT 0"))
        if "model_call_logs" in table_names:
            call_log_columns = {column["name"] for column in inspector.get_columns("model_call_logs")}
            if "project_id" not in call_log_columns:
                conn.execute(text("ALTER TABLE model_call_logs ADD COLUMN project_id VARCHAR(64) NULL"))


def main() -> None:
    ensure_database_exists()
    Base.metadata.create_all(bind=engine)
    run_compat_migrations()
    with SessionLocal() as db:
        seed_database(db)
    print("Database initialized and seeded.")


if __name__ == "__main__":
    main()
