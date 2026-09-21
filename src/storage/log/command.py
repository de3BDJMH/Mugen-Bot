import sqlite3

def init(conn:sqlite3.Connection):
    """初始化commands表"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS commands(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            command_key TEXT NOT NULL,
            args_json TEXT NOT NULL,
            FOREIGN KEY(message_id) REFERENCES messages(id)
        );

        CREATE INDEX IF NOT EXISTS idx_commands_message_id
        ON commands(message_id);

        CREATE INDEX IF NOT EXISTS idx_commands_key
        ON commands(command_key);
    """)

def add(conn:sqlite3.Connection,message_id:int,command_key:str,args_json:str):
    """存储"""
    cursor=conn.execute("""
        INSERT INTO commands(message_id,command_key,args_json)
        VALUES(?,?,?)
    """,(message_id,command_key,args_json))
    return cursor.lastrowid