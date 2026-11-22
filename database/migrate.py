import asyncio
import logging
from pathlib import Path
from sqlalchemy import text
from database.db import engine, init_db, close_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _extract_sql_statements(sql_content: str) -> list[str]:
    """Strip `--` SQL comment lines and split into executable statements."""
    active_lines: list[str] = []
    for line in sql_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        active_lines.append(line)
    cleaned_sql = "\n".join(active_lines)
    return [stmt.strip() for stmt in cleaned_sql.split(";") if stmt.strip()]


async def run_migrations() -> None:
    logger.info("Starting database migrations...")
    await init_db()

    if MIGRATIONS_DIR.exists():
        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        async with engine.begin() as conn:
            for sql_file in sql_files:
                logger.info("Applying migration file: %s", sql_file.name)
                sql_content = sql_file.read_text(encoding="utf-8")
                statements = _extract_sql_statements(sql_content)
                for stmt in statements:
                    await conn.execute(text(stmt))

    logger.info("All database migrations applied successfully.")
    await close_db()


if __name__ == "__main__":
    asyncio.run(run_migrations())
