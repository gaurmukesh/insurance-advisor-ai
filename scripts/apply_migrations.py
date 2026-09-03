"""
Applies SQL migration files in order, recording each one in a schema_migrations
ledger table so a deploy only re-runs files that haven't landed yet.

Replaces a plain `psql -f` loop: that loop re-applies every file on every deploy
and depends entirely on each .sql file being hand-written as idempotent
(IF NOT EXISTS, etc.) to be safe. This adds an explicit, queryable record of
what has actually been applied to a given database and when, so a migration
that silently gets dropped from the list (the original prod-schema-migrations
bug) or fails partway through is visible instead of assumed.

Usage: python scripts/apply_migrations.py <db_url> migrations/init.sql migrations/agents.sql ...
<db_url> must be a plain libpq-compatible postgresql:// URI (not asyncpg-prefixed).
"""

import sys

import psycopg2

CREATE_LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _split_statements(sql: str) -> list[str]:
    # Sending a whole file as one multi-statement string makes Postgres wrap it
    # in an implicit transaction even under autocommit, which breaks statements
    # like CREATE INDEX CONCURRENTLY (hnsw_index.sql). psql avoids this by
    # issuing each statement as its own protocol message; do the same here.
    #
    # Strip `--` line comments before splitting: a comment can itself contain a
    # ";" (e.g. mcp_tokens.sql: "-- token is ever handed to a client;"), which
    # would otherwise be mistaken for a statement terminator. None of the
    # current files use /* */ comments, dollar-quoted bodies, or a literal ";"
    # inside a string.
    lines = (line[: line.find("--")] if "--" in line else line for line in sql.splitlines())
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: apply_migrations.py <db_url> <migration_file>...", file=sys.stderr)
        sys.exit(1)

    db_url, files = sys.argv[1], sys.argv[2:]

    conn = psycopg2.connect(db_url)
    # Autocommit, not a transaction per file: some migrations (e.g.
    # hnsw_index.sql) use CREATE INDEX CONCURRENTLY, which errors inside an
    # explicit transaction block. This also matches plain `psql -f` semantics,
    # which the previous CI step relied on.
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_LEDGER)

        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        for path in files:
            name = path.rsplit("/", 1)[-1]
            if name in applied:
                print(f"Skipping {path} (already applied)")
                continue

            print(f"Applying {path}")
            with open(path) as f:
                statements = _split_statements(f.read())

            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (name,))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
