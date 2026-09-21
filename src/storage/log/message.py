import sqlite3

def init(conn:sqlite3.Connection):
    """初始化messages表"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            self_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            group_id INTEGER,
            sender_id INTEGER NOT NULL,
            time INTEGER NOT NULL,
            message_json TEXT NOT NULL,
            plain_text TEXT NOT NULL,
            UNIQUE(self_id,message_id)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_group_time
        ON messages(group_id,time);

        CREATE INDEX IF NOT EXISTS idx_messages_sender_time
        ON messages(sender_id,time);
    """)

def add(conn:sqlite3.Connection,message_id:int,self_id:int,type:str,group_id:int|None,sender_id:int,time:int,message_json:str,plain_text:str):
    """存储"""
    cursor=conn.execute("""
        INSERT INTO messages(message_id,self_id,type,group_id,sender_id,time,message_json,plain_text)
        VALUES(?,?,?,?,?,?,?,?)
    """,(message_id,self_id,type,group_id,sender_id,time,message_json,plain_text))
    return cursor.lastrowid

def get_id_by_message_id(conn:sqlite3.Connection,message_id:int,self_id:int)->int|None:
    """根据message_id获取id，需要同时传入self_id（botQQ）"""
    row=conn.execute("""
        SELECT id FROM messages
        WHERE self_id=? AND message_id=?
    """,(self_id,message_id)).fetchone()

    return row["id"] if row else None