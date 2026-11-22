from config import normalize_database_url


def test_render_internal_and_external_database_urls() -> None:
    # Render internal URL (uses postgres:// and no port)
    render_internal = "postgres://myuser:mypass@dpg-ct1234567890-a/english_c2_bot"
    assert (
        normalize_database_url(render_internal)
        == "postgresql+asyncpg://myuser:mypass@dpg-ct1234567890-a/english_c2_bot"
    )

    # Render external URL (uses postgres:// or postgresql:// with domain)
    render_external = "postgresql://myuser:mypass@dpg-ct1234567890-a.oregon-postgres.render.com/english_c2_bot"
    assert (
        normalize_database_url(render_external)
        == "postgresql+asyncpg://myuser:mypass@dpg-ct1234567890-a.oregon-postgres.render.com/english_c2_bot"
    )

    # URL with psycopg2 driver explicitly specified
    psycopg2_url = "postgresql+psycopg2://postgres:password@localhost:5432/english_c2_bot"
    assert (
        normalize_database_url(psycopg2_url)
        == "postgresql+asyncpg://postgres:password@localhost:5432/english_c2_bot"
    )

    # URL with sslmode=require
    ssl_url = "postgres://myuser:mypass@host:5432/dbname?sslmode=require"
    assert (
        normalize_database_url(ssl_url)
        == "postgresql+asyncpg://myuser:mypass@host:5432/dbname?ssl=require"
    )

    # URL wrapped in quotes in env var
    quoted_url = '"postgres://myuser:mypass@dpg-ct1234567890-a/english_c2_bot"'
    assert (
        normalize_database_url(quoted_url)
        == "postgresql+asyncpg://myuser:mypass@dpg-ct1234567890-a/english_c2_bot"
    )
