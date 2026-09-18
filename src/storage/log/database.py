from contextlib import contextmanager
import pathlib
import sqlite3

from . import message

ROOT_PATH=pathlib.Path(__file__).parent.parent.parent.parent#/server
DATA_PATH=ROOT_PATH/"data"/"log"
DATA_PATH.mkdir(parents=True,exist_ok=True)#确保目录存在

def connect()->sqlite3.Connection:
    conn=sqlite3.connect(DATA_PATH/"logs.db")
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def transaction():
    """事务"""
    conn=connect()
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """初始化数据库"""
    conn=connect()
    try:
        message.init(conn)
        conn.commit()
    finally:
        conn.close()