def init(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS release (
            id INTEGER PRIMARY KEY
        )
    """)

def is_sent(conn, release_id):
    return conn.execute(
        "SELECT 1 FROM release WHERE id=?",
        (release_id,)
    ).fetchone() is not None

def record_sent(conn, release_id):
    conn.execute(
        "INSERT OR IGNORE INTO release VALUES (?)",
        (release_id,)
    )