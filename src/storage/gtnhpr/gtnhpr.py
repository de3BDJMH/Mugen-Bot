import sqlite3
from pathlib import Path

ROOT_PATH=Path(__file__).parent.parent.parent.parent
DATA_PATH=ROOT_PATH/"data"/"gtnhpr"
DB_PATH=DATA_PATH/"pr.db"

def connect() ->sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init(conn:sqlite3.Connection):
    """初始化数据库"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gtnhpr (
            pr_id INTEGER PRIMARY KEY,
            url TEXT NOT NULL,
            image BLOB NOT NULL,
            sent_at TEXT NOT NULL
        )
    """)

def save_pr(conn:sqlite3.Connection,pr_id:int,url:str,image:bytes,sent_at:str):
    """保存一条PR"""
    conn.execute(
        """
        INSERT INTO gtnhpr (pr_id,url,image,sent_at)
        VALUES (?,?,?,?)
        """,
        (pr_id,url,image,sent_at)
    )

def get_last_pr(conn:sqlite3.Connection,limit:int=5):
    """读取最后n次推送的 PR"""
    return conn.execute(
        """
        SELECT url, image
        FROM gtnhpr
        ORDER BY sent_at DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

def has_pr(conn:sqlite3.Connection, pr_id:int)->bool:
    """判断指定PR是否已经推送"""
    result=conn.execute(
        "SELECT 1 FROM gtnhpr WHERE pr_id = ?",
        (pr_id,)
    ).fetchone()

    return result is not None
