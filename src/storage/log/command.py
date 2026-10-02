import sqlite3

def init(conn:sqlite3.Connection):
    """初始化commands表"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS commands(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            command_key TEXT NOT NULL,
            params_json TEXT NOT NULL DEFAULT '{}',
            valid INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_commands_message_id
        ON commands(message_id);
    """)

def add(conn:sqlite3.Connection,message_id:int,command_key:str,valid:int,params_json:str):
    """添加一条命令记录"""
    cursor=conn.execute(
        "INSERT INTO commands(message_id,command_key,valid,params_json) VALUES(?,?,?,?)",
        (message_id,command_key,valid,params_json)
    )
    return cursor.lastrowid