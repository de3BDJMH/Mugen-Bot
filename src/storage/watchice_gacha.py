import sqlite3
import pathlib
import datetime

DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent/"data"/"watchice_gacha"
DB_PATH=DATA_PATH/"database"/"gacha.db"

def _connect()->sqlite3.Connection:
    conn=sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_database():
    """初始化抽卡数据库"""
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)

    conn=_connect()
    cursor=conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_cards(
            user_id INTEGER NOT NULL,
            image_id INTEGER NOT NULL,
            owned_count INTEGER NOT NULL DEFAULT 1,
            first_obtained_at TEXT NOT NULL,

            PRIMARY KEY(user_id,image_id),

            CHECK(owned_count>0)
        );

        CREATE TABLE IF NOT EXISTS gacha_draws(
            draw_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            request_id TEXT NOT NULL,
            count INTEGER NOT NULL,

            cost_base INTEGER NOT NULL,
            cost_addition REAL NOT NULL,
            cost_zero INTEGER NOT NULL,

            created_at TEXT NOT NULL,

            UNIQUE(user_id,request_id),

            CHECK(count IN (1,10))
        );

        CREATE TABLE IF NOT EXISTS gacha_draw_items(
            draw_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            image_id INTEGER NOT NULL,
            is_new INTEGER NOT NULL,
            copies_after INTEGER NOT NULL,

            PRIMARY KEY(draw_id,position),

            FOREIGN KEY(draw_id) REFERENCES gacha_draws(draw_id),

            CHECK(position>0),
            CHECK(copies_after>0)
        );
        """
    )

    conn.commit()
    conn.close()
init_database()

def add_user_card_conn(
    conn:sqlite3.Connection,
    user_id:int,
    image_id:int,
    obtained_at:datetime.datetime
)->dict:
    """用户获得一张卡"""
    cursor=conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO user_cards(
            user_id,
            image_id,
            owned_count,
            first_obtained_at
        )
        VALUES(?,?,?,?)
        """,
        (
            user_id,
            image_id,
            1,
            obtained_at.isoformat(timespec="seconds")
        )
    )

    if cursor.rowcount>0:
        return {
            "image_id":image_id,
            "is_new":True,
            "copies_after":1
        }

    cursor.execute(
        """
        UPDATE user_cards
        SET owned_count=owned_count+1
        WHERE user_id=? AND image_id=?
        """,
        (user_id,image_id)
    )

    cursor.execute(
        """
        SELECT owned_count
        FROM user_cards
        WHERE user_id=? AND image_id=?
        """,
        (user_id,image_id)
    )

    return {
        "image_id":image_id,
        "is_new":False,
        "copies_after":cursor.fetchone()[0]
    }

def get_user_cards(user_id:int)->list[dict]:
    """获取用户持卡"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT image_id,owned_count,first_obtained_at
        FROM user_cards
        WHERE user_id=?
        ORDER BY image_id
        """,
        (user_id,)
    )

    rows=cursor.fetchall()
    conn.close()

    return [
        {
            "image_id":row[0],
            "owned_count":row[1],
            "first_obtained_at":datetime.datetime.fromisoformat(row[2])
        }
        for row in rows
    ]

def get_user_card(user_id:int,image_id:int)->dict|None:
    """获取用户指定持卡"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT owned_count,first_obtained_at
        FROM user_cards
        WHERE user_id=? AND image_id=?
        """,
        (user_id,image_id)
    )

    row=cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "image_id":image_id,
        "owned_count":row[0],
        "first_obtained_at":datetime.datetime.fromisoformat(row[1])
    }

def create_draw_conn(
    conn:sqlite3.Connection,
    user_id:int,
    request_id:str,
    count:int,
    cost_base:int,
    cost_addition:float,
    cost_zero:bool,
    created_at:datetime.datetime
)->int:
    """创建一次抽卡记录"""
    cursor=conn.cursor()

    cursor.execute(
        """
        INSERT INTO gacha_draws(
            user_id,
            request_id,
            count,
            cost_base,
            cost_addition,
            cost_zero,
            created_at
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            user_id,
            request_id,
            count,
            cost_base,
            cost_addition,
            cost_zero,
            created_at.isoformat(timespec="seconds")
        )
    )

    return cursor.lastrowid

def add_draw_items_conn(
    conn:sqlite3.Connection,
    draw_id:int,
    items:list[dict]
)->None:
    """添加一次抽卡的全部结果"""
    cursor=conn.cursor()

    cursor.executemany(
        """
        INSERT INTO gacha_draw_items(
            draw_id,
            position,
            image_id,
            is_new,
            copies_after
        )
        VALUES(?,?,?,?,?)
        """,
        [
            (
                draw_id,
                item["position"],
                item["image_id"],
                item["is_new"],
                item["copies_after"]
            )
            for item in items
        ]
    )

def get_draw_by_request_id_conn(conn:sqlite3.Connection,user_id:int,request_id:str)->dict|None:
    """使用指定连接根据request_id获取抽卡记录"""
    cursor=conn.cursor()
    cursor.execute(
        """
        SELECT draw_id,count,cost_base,cost_addition,cost_zero,created_at
        FROM gacha_draws
        WHERE user_id=? AND request_id=?
        """,
        (user_id,request_id)
    )
    row=cursor.fetchone()

    if row is None:
        return None

    return {
        "draw_id":row[0],
        "count":row[1],
        "cost_base":row[2],
        "cost_addition":row[3],
        "cost_zero":bool(row[4]),
        "created_at":datetime.datetime.fromisoformat(row[5])
    }

def get_draw_by_request_id(user_id:int,request_id:str)->dict|None:
    conn=_connect()
    result=get_draw_by_request_id_conn(conn,user_id,request_id)
    conn.close()
    return result

def get_draw_items_conn(conn:sqlite3.Connection,draw_id:int)->list[dict]:
    """使用指定连接获取一次抽卡的全部结果"""
    cursor=conn.cursor()
    cursor.execute(
        """
        SELECT position,image_id,is_new,copies_after
        FROM gacha_draw_items
        WHERE draw_id=?
        ORDER BY position
        """,
        (draw_id,)
    )

    return [
        {
            "position":row[0],
            "image_id":row[1],
            "is_new":bool(row[2]),
            "copies_after":row[3]
        }
        for row in cursor.fetchall()
    ]

def get_draw_items(draw_id:int)->list[dict]:
    conn=_connect()
    result=get_draw_items_conn(conn,draw_id)
    conn.close()
    return result

def get_user_draw_history(user_id:int,page:int=1,page_size:int=20)->dict:
    """获取用户抽卡历史"""
    page=max(page,1)
    page_size=max(1,min(page_size,50))
    offset=(page-1)*page_size

    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM gacha_draws
        WHERE user_id=?
        """,
        (user_id,)
    )
    total=cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT
            d.draw_id,
            d.request_id,
            d.count,
            d.cost_base,
            d.cost_addition,
            d.cost_zero,
            d.created_at,
            i.position,
            i.image_id,
            i.is_new,
            i.copies_after
        FROM (
            SELECT *
            FROM gacha_draws
            WHERE user_id=?
            ORDER BY draw_id DESC
            LIMIT ? OFFSET ?
        ) AS d
        LEFT JOIN gacha_draw_items AS i
        ON i.draw_id=d.draw_id
        ORDER BY d.draw_id DESC,i.position ASC
        """,
        (user_id,page_size,offset)
    )

    rows=cursor.fetchall()
    conn.close()

    draws={}

    for row in rows:
        draw_id=row[0]

        if draw_id not in draws:
            draws[draw_id]={
                "draw_id":draw_id,
                "request_id":row[1],
                "count":row[2],
                "cost_base":row[3],
                "cost_addition":row[4],
                "cost_zero":bool(row[5]),
                "created_at":datetime.datetime.fromisoformat(row[6]),
                "items":[]
            }

        if row[7] is not None:
            draws[draw_id]["items"].append({
                "position":row[7],
                "image_id":row[8],
                "is_new":bool(row[9]),
                "copies_after":row[10]
            })

    return {
        "page":page,
        "page_size":page_size,
        "total":total,
        "items":list(draws.values())
    }