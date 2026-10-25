import re
import sqlite3
import time
from pathlib import Path

ROOT_PATH=Path(__file__).parent.parent.parent.parent
DATA_PATH=ROOT_PATH/"data"/"gtnhpr"
DB_PATH=DATA_PATH/"knowledge.db"

def connect():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS search_cache(
        query TEXT PRIMARY KEY,
        result TEXT NOT NULL,
        saved_at INTEGER NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge(
        url TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        saved_at INTEGER NOT NULL
    )""")
    conn.commit()

def lookup(query:str):
    """搜索知识库"""
    conn=connect()
    try:
        init(conn)
        now=int(time.time())

        row=conn.execute(
            "SELECT result FROM search_cache WHERE query=? AND saved_at>=?",
            (query,now-14*86400)
        ).fetchone()
        if row:return "cache",row[0]

        words=re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2,}",query.lower())
        words=[w for w in words if w not in ("gtnh","wiki","是什么","怎么","修复","功能","机制")]
        if len(words)<2:
            return None,None

        rows=conn.execute(
            "SELECT title,url,summary FROM knowledge WHERE saved_at>=?",
            (now-30*86400,)
        ).fetchall()

        matches=[]
        for title,url,summary in rows:
            content=(title+" "+summary).lower()
            score=sum(w in content for w in words)
            if score>=2 and score*2>=len(words):
                matches.append((score,title,url,summary))

        matches.sort(reverse=True)
        if not matches:
            return None,None

        text="\n\n".join(
            f"资料：{title}\n来源：{url}\n内容：{summary}"
            for _,title,url,summary in matches[:3]
        )
        return "knowledge",text
    finally:
        conn.close()

def save(query:str,results:list[dict]):
    """保存查到的信息（知识）"""
    conn=connect()
    try:
        init(conn)
        now=int(time.time())
        text="\n\n".join(
            f"资料：{x['title']}\n来源：{x['url']}\n内容：{x['summary']}"
            for x in results
        ) or "未找到相关资料"

        conn.execute(
            "INSERT OR REPLACE INTO search_cache VALUES(?,?,?)",
            (query,text,now)
        )
        for x in results:
            conn.execute(
                "INSERT OR REPLACE INTO knowledge VALUES(?,?,?,?)",
                (x["url"],x["title"],x["summary"],now)
            )
        conn.commit()
        return text
    finally:
        conn.close()
