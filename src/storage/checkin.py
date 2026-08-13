import sqlite3
import pathlib
import json
import datetime
from zoneinfo import ZoneInfo

DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent/"data"/"checkin"/"data"/"checkin.db"

def init_database():
    """初始化签到数据库"""
    DATA_PATH.parent.mkdir(parents=True,exist_ok=True)

    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            nickname TEXT NOT NULL,
            last_checkin TEXT,
            total INTEGER NOT NULL DEFAULT 0,
            consecutive INTEGER NOT NULL DEFAULT 0,
            max_consecutive INTEGER NOT NULL DEFAULT 0,
            data_base INTEGER NOT NULL,
            data_addition REAL NOT NULL,
            data_zero INTEGER NOT NULL,
            rob_rate REAL NOT NULL,
            last_rob TEXT
        );

        CREATE TABLE IF NOT EXISTS user_items(
            user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY(user_id,item_id)
        );

        CREATE TABLE IF NOT EXISTS rob_records(
            user_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            success_times INTEGER NOT NULL DEFAULT 0,
            fail_times INTEGER NOT NULL DEFAULT 0,
            success_data_base INTEGER NOT NULL,
            success_data_addition REAL NOT NULL,
            success_data_zero INTEGER NOT NULL,
            fail_data_base INTEGER NOT NULL,
            fail_data_addition REAL NOT NULL,
            fail_data_zero INTEGER NOT NULL,
            PRIMARY KEY(user_id,target_user_id)
        );

        CREATE TABLE IF NOT EXISTS checkin_time(
            user_id INTEGER NOT NULL,
            checkin_date TEXT NOT NULL,
            checkin_at TEXT NOT NULL,
            PRIMARY KEY(user_id,checkin_date)
        );

        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            operation TEXT NOT NULL,
            change_type TEXT,
            related_user_id INTEGER,
            data_base INTEGER,
            data_addition REAL,
            data_zero INTEGER,
            item_id INTEGER,
            item_count INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_rob_records_target
        ON rob_records(target_user_id);

        CREATE INDEX IF NOT EXISTS idx_logs_user_created
        ON logs(user_id,created_at);
    """)

    conn.commit()
    conn.close()
init_database()

###
#签到数据操作
###

def add_checkin(user_id:int,checkin_at:datetime.datetime):
    """
    添加签到记录
    """
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    checkin_date=checkin_at.date().isoformat()
    cursor.execute("INSERT OR IGNORE INTO checkin_time (user_id, checkin_date, checkin_at) VALUES (?, ?, ?)", (user_id, checkin_date, checkin_at.isoformat()))
    conn.commit()
    conn.close()

def get_all_checkin_data()->list[dict]:
    """
    获取所有签到数据
    """
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    cursor.execute("SELECT user_id, checkin_date, checkin_at FROM checkin_time ORDER BY checkin_date ASC, checkin_at ASC")
    data=[{"user_id":row[0],"checkin_date":datetime.date.fromisoformat(row[1]),"checkin_at":datetime.datetime.fromisoformat(row[2])} for row in cursor.fetchall()]
    conn.close()
    return data

def get_checkin_dates(user_id:int,date_range:tuple[datetime.date,datetime.date]=None)->list[datetime.date]:
    """
    获取用户签到日期列表
    """
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    if date_range:
        cursor.execute("SELECT checkin_date FROM checkin_time WHERE user_id = ? AND checkin_date BETWEEN ? AND ? ORDER BY checkin_date ASC", (user_id, date_range[0].isoformat(), date_range[1].isoformat()))
    else:
        cursor.execute("SELECT checkin_date FROM checkin_time WHERE user_id = ?", (user_id,))
    dates=[datetime.date.fromisoformat(row[0]) for row in cursor.fetchall()]
    conn.close()
    return dates

def get_checkin_by_date(checkin_date:datetime.date)->list[list[int, datetime.datetime]]:
    """
    获取指定日期的签到用户列表
    """
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    cursor.execute("SELECT user_id, checkin_at FROM checkin_time WHERE checkin_date = ? ORDER BY checkin_at ASC", (checkin_date.isoformat(),))
    users=[[row[0], datetime.datetime.fromisoformat(row[1])] for row in cursor.fetchall()]
    conn.close()
    return users

def has_checked(user_id:int,checkin_date:datetime.date)->bool:
    """
    检查用户在指定日期是否签到
    """
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    cursor.execute("SELECT 1 FROM checkin_time WHERE user_id = ? AND checkin_date = ?", (user_id, checkin_date.isoformat()))
    result=cursor.fetchone()
    conn.close()
    return result is not None

def get_checkin_time(user_id:int,checkin_date:datetime.date)->datetime.datetime|None:
    """
    获取用户在这天签到的时间
    """
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    cursor.execute(
        "SELECT checkin_at FROM checkin_time WHERE user_id=? AND checkin_date=?",
        (user_id,checkin_date.isoformat())
    )
    row=cursor.fetchone()
    conn.close()

    if row:
        return datetime.datetime.fromisoformat(row[0])
    return None

def get_last_checkin(user_id:int)->datetime.datetime:
    """
    获取用户最后一次签到时间
    """
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    cursor.execute("SELECT checkin_at FROM checkin_time WHERE user_id = ? ORDER BY checkin_at DESC LIMIT 1", (user_id,))
    row=cursor.fetchone()
    conn.close()
    if row:
        return datetime.datetime.fromisoformat(row[0])
    return None

def get_last_checkin_date(before:datetime.date)->datetime.date|None:
    """获取指定日期及以前最近一个有签到记录的日期"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    cursor.execute(
        """
        SELECT checkin_date
        FROM checkin_time
        WHERE checkin_date<=?
        ORDER BY checkin_date DESC
        LIMIT 1
        """,
        (before.isoformat(),)
    )
    row=cursor.fetchone()
    conn.close()

    if row:
        return datetime.date.fromisoformat(row[0])
    return None

def get_checkin_rank(user_id:int,checkin_date:datetime.date)->int:
    """
    获取用户在指定日期的签到排名
    """
    users=get_checkin_by_date(checkin_date)
    for rank,user in enumerate(users,1):
        if user[0]==user_id:
            return rank
    return None

def get_user_calendar_records(user_id:int,start:datetime.date,end:datetime.date)->list[dict]:
    """获取用户指定日期范围内的签到时间与排名"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT checkin_date,checkin_at,rank
        FROM(
            SELECT
                user_id,
                checkin_date,
                checkin_at,
                ROW_NUMBER() OVER(
                    PARTITION BY checkin_date
                    ORDER BY checkin_at ASC,user_id ASC
                ) AS rank
            FROM checkin_time
            WHERE checkin_date>=? AND checkin_date<=?
        )
        WHERE user_id=?
        ORDER BY checkin_date ASC
        """,
        (
            start.isoformat(),
            end.isoformat(),
            user_id
        )
    )

    records=[
        {
            "date":datetime.date.fromisoformat(row[0]),
            "checkin_at":datetime.datetime.fromisoformat(row[1]),
            "rank":row[2]
        }
        for row in cursor.fetchall()
    ]

    conn.close()
    return records

###
#日志数据操作
###

def add_log(
    user_id:int,
    operation:str,
    change_type:str,
    data_base:int|None,
    data_addition:float|None,
    data_zero:bool|None,
    created_at:datetime.datetime,
    related_user_id:int|None=None,
    item_id:int|None=None,
    item_count:int|None=None
):
    """添加一条签到系统日志记录"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()
    cursor.execute(
        """
        INSERT INTO logs(
            user_id,
            operation,
            change_type,
            related_user_id,
            data_base,
            data_addition,
            data_zero,
            item_id,
            item_count,
            created_at
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            user_id,
            operation,
            change_type,
            related_user_id,
            data_base,
            data_addition,
            data_zero,
            item_id,
            item_count,
            created_at.isoformat(timespec="seconds")
        )
    )
    conn.commit()
    conn.close()

def _log_row_to_dict(row):
    """日志记录转换为字典（历史遗留问题，以前用的json"""
    log={
        "id":row[0],
        "operate":row[1],
        "type":row[2],
        "related_user_id":row[3],
        "time":datetime.datetime.fromisoformat(row[9]).strftime("%Y-%m-%d %H:%M:%S")
    }

    if row[4] is not None:
        log["data"]={
            "base":row[4],
            "addition":row[5],
            "zero":bool(row[6])
        }
    if row[7] is not None:
        log["item"]={
            "item_id":row[7],
            "count":row[8]
        }

    return log

def get_user_logs(user_id:int,lines:int=-1):
    """获取用户日志，lines为返回的最近日志条数，-1表示全部"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    if lines==-1:
        cursor.execute(
            """
            SELECT id,operation,change_type,related_user_id,
                   data_base,data_addition,data_zero,
                   item_id,item_count,created_at
            FROM logs
            WHERE user_id=?
            ORDER BY created_at ASC
            """,
            (user_id,)
        )
        rows=cursor.fetchall()
    else:
        cursor.execute(
            """
            SELECT id,operation,change_type,related_user_id,
                   data_base,data_addition,data_zero,
                   item_id,item_count,created_at
            FROM logs
            WHERE user_id=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id,lines)
        )
        rows=cursor.fetchall()[::-1]

    conn.close()
    return [_log_row_to_dict(row) for row in rows]

def get_user_logs_by_date(user_id:int,date:datetime.date):
    """
    获取用户指定日期的日志
    """
    start=datetime.datetime.combine(date,datetime.time.min,tzinfo=ZoneInfo("Asia/Shanghai"))
    end=start+datetime.timedelta(days=1)

    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT id,operation,change_type,related_user_id,
               data_base,data_addition,data_zero,
               item_id,item_count,created_at
        FROM logs
        WHERE user_id=?
        AND created_at>=?
        AND created_at<?
        ORDER BY created_at ASC
        """,
        (
            user_id,
            start.isoformat(timespec="seconds"),
            end.isoformat(timespec="seconds")
        )
    )

    rows=cursor.fetchall()
    conn.close()

    return [_log_row_to_dict(row) for row in rows]

###
#用户数据操作
###

def get_user(user_id:int)->dict|None:
    """获取用户数据，不存在时返回None"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT
            user_id,nickname,last_checkin,total,consecutive,max_consecutive,
            data_base,data_addition,data_zero,rob_rate,last_rob
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row=cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "user_id":row[0],
        "nickname":row[1],
        "last_checkin":datetime.date.fromisoformat(row[2]) if row[2] else None,
        "total":row[3],
        "consecutive":row[4],
        "max_consecutive":row[5],
        "data_base":row[6],
        "data_addition":row[7],
        "data_zero":bool(row[8]),
        "rob_rate":row[9],
        "last_rob":datetime.datetime.fromisoformat(row[10]) if row[10] else None
    }

def create_user(user_id:int,nickname:str="")->None:
    """创建用户，用户已存在时不重复创建"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO users(
            user_id,nickname,last_checkin,total,consecutive,max_consecutive,
            data_base,data_addition,data_zero,rob_rate,last_rob
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            user_id,
            nickname,
            None,
            0,
            0,
            0,
            0,
            0.0,
            True,
            0.5,
            datetime.datetime(1970,1,1,tzinfo=ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
        )
    )

    conn.commit()
    conn.close()

def update_user(user_id:int,nickname:str,last_checkin:datetime.date|None,total:int,consecutive:int,max_consecutive:int,data_base:int,data_addition:float,data_zero:bool,rob_rate:float,last_rob:datetime.datetime)->None:
    """更新用户基础信息与Data数据"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET
            nickname=?,
            last_checkin=?,
            total=?,
            consecutive=?,
            max_consecutive=?,
            data_base=?,
            data_addition=?,
            data_zero=?,
            rob_rate=?,
            last_rob=?
        WHERE user_id=?
        """,
        (
            nickname,
            last_checkin.isoformat() if last_checkin else None,
            total,
            consecutive,
            max_consecutive,
            data_base,
            data_addition,
            data_zero,
            rob_rate,
            last_rob.isoformat(timespec="seconds"),
            user_id
        )
    )

    conn.commit()
    conn.close()

###
#用户物品操作
###

def get_user_items(user_id:int)->dict[int,dict]:
    """获取用户所有物品"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT item_id,item_name,count
        FROM user_items
        WHERE user_id=?
        """,
        (user_id,)
    )

    items={
        row[0]:{
            "name":row[1],
            "count":row[2]
        }
        for row in cursor.fetchall()
    }

    conn.close()
    return items

def add_user_item(user_id:int,item_id:int,item_name:str,count:int=1)->None:
    """增加用户物品"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        INSERT INTO user_items(
            user_id,item_id,item_name,count
        )
        VALUES(?,?,?,?)
        ON CONFLICT(user_id,item_id)
        DO UPDATE SET
            item_name=excluded.item_name,
            count=user_items.count+excluded.count
        """,
        (user_id,item_id,item_name,count)
    )

    conn.commit()
    conn.close()

###
#抢劫数据操作
###

def get_rob_records(user_id:int)->dict[int,dict]:
    """获取用户所有抢劫记录"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT
            target_user_id,
            success_times,
            fail_times,
            success_data_base,
            success_data_addition,
            success_data_zero,
            fail_data_base,
            fail_data_addition,
            fail_data_zero
        FROM rob_records
        WHERE user_id=?
        """,
        (user_id,)
    )

    records={}
    for row in cursor.fetchall():
        records[row[0]]={
            "success_times":row[1],
            "fail_times":row[2],
            "success_data":{
                "base":row[3],
                "addition":row[4],
                "zero":bool(row[5])
            },
            "fail_data":{
                "base":row[6],
                "addition":row[7],
                "zero":bool(row[8])
            }
        }

    conn.close()
    return records

def update_rob_record(user_id:int,target_user_id:int,record:dict)->None:
    """更新用户对指定目标的抢劫统计"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        INSERT INTO rob_records(
            user_id,
            target_user_id,
            success_times,
            fail_times,
            success_data_base,
            success_data_addition,
            success_data_zero,
            fail_data_base,
            fail_data_addition,
            fail_data_zero
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id,target_user_id)
        DO UPDATE SET
            success_times=excluded.success_times,
            fail_times=excluded.fail_times,
            success_data_base=excluded.success_data_base,
            success_data_addition=excluded.success_data_addition,
            success_data_zero=excluded.success_data_zero,
            fail_data_base=excluded.fail_data_base,
            fail_data_addition=excluded.fail_data_addition,
            fail_data_zero=excluded.fail_data_zero
        """,
        (
            user_id,
            target_user_id,
            record["success_times"],
            record["fail_times"],
            record["success_data"]["base"],
            record["success_data"]["addition"],
            record["success_data"]["zero"],
            record["fail_data"]["base"],
            record["fail_data"]["addition"],
            record["fail_data"]["zero"]
        )
    )

    conn.commit()
    conn.close()

def get_robbed_by(user_id:int)->list[int]:
    """获取抢劫过指定用户的用户列表"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT user_id
        FROM rob_records
        WHERE target_user_id=?
        """,
        (user_id,)
    )

    users=[row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_all_rob_records()->list[dict]:
    """获取全部抢劫记录"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute("""
        SELECT
            r.user_id,
            u.nickname,
            r.target_user_id,
            t.nickname,
            r.success_times,
            r.fail_times,
            r.success_data_base,
            r.success_data_addition,
            r.success_data_zero,
            r.fail_data_base,
            r.fail_data_addition,
            r.fail_data_zero
        FROM rob_records r
        JOIN users u ON r.user_id=u.user_id
        JOIN users t ON r.target_user_id=t.user_id
    """)

    rows=cursor.fetchall()
    conn.close()

    return [{
        "user_id":row[0],
        "user_nickname":row[1],
        "target_id":row[2],
        "target_nickname":row[3],
        "success_times":row[4],
        "fail_times":row[5],
        "success_data":{
            "base":row[6],
            "addition":row[7],
            "zero":bool(row[8])
        },
        "fail_data":{
            "base":row[9],
            "addition":row[10],
            "zero":bool(row[11])
        }
    } for row in rows]

def get_rob_records_by_target(target_user_id:int)->list[dict]:
    """获取以指定用户为目标的全部抢劫统计记录"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute("""
        SELECT
            r.user_id,
            u.nickname,
            r.success_times,
            r.fail_times,
            r.success_data_base,
            r.success_data_addition,
            r.success_data_zero,
            r.fail_data_base,
            r.fail_data_addition,
            r.fail_data_zero
        FROM rob_records r
        JOIN users u ON u.user_id=r.user_id
        WHERE r.target_user_id=?
    """,(target_user_id,))

    rows=cursor.fetchall()
    conn.close()

    return [{
        "user_id":row[0],
        "nickname":row[1],
        "success_times":row[2],
        "fail_times":row[3],
        "success_data":{
            "base":row[4],
            "addition":row[5],
            "zero":bool(row[6])
        },
        "fail_data":{
            "base":row[7],
            "addition":row[8],
            "zero":bool(row[9])
        }
    } for row in rows]

def get_all_user_data()->list[dict]:
    """获取所有用户的Data数据"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute("""
        SELECT user_id,nickname,data_base,data_addition,data_zero
        FROM users
    """)

    rows=cursor.fetchall()
    conn.close()

    return [{
        "user_id":row[0],
        "nickname":row[1],
        "base":row[2],
        "addition":row[3],
        "zero":bool(row[4])
    } for row in rows]

def get_user_nicknames()->dict[int,str]:
    """获取用户ID与昵称的映射"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute("SELECT user_id,nickname FROM users")
    rows=cursor.fetchall()

    conn.close()

    return {row[0]:row[1] for row in rows}

def update_user_nickname(user_id:int,nickname:str)->None:
    """更新指定用户的昵称"""
    conn=sqlite3.connect(DATA_PATH)
    cursor=conn.cursor()

    cursor.execute(
        "UPDATE users SET nickname=? WHERE user_id=?",
        (nickname,user_id)
    )

    conn.commit()
    conn.close()