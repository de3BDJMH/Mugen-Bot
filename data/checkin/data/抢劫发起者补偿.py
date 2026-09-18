import sqlite3
from pathlib import Path

DB_PATH=Path(__file__).resolve().parent/"checkin.db"
DRY_RUN=False

def is_pair(a:sqlite3.Row,b:sqlite3.Row) -> bool:
    """判断两条日志是否属于同一次抢劫"""
    return (
        a["user_id"]==b["related_user_id"]
        and a["related_user_id"]==b["user_id"]
        and a["created_at"]==b["created_at"]
        and a["change_type"]!=b["change_type"]
        and a["data_base"]==b["data_base"]
        and a["data_addition"]==b["data_addition"]
        and a["data_zero"]==b["data_zero"]
    )

def migrate():
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    cursor=conn.cursor()

    logs=cursor.execute("""
        SELECT id,user_id,related_user_id,change_type,data_base,data_addition,data_zero,created_at
        FROM logs
        WHERE operation='rob' AND detail IS NULL
        ORDER BY id
    """).fetchall()

    pairs=[]
    failed=[]
    i=0

    while i<len(logs):
        if i+1>=len(logs):
            failed.append(logs[i])
            break

        a=logs[i]
        b=logs[i+1]

        if is_pair(a,b):
            pairs.append((a,b))
            i+=2
        else:
            failed.append(a)
            i+=1

    print(f"共找到 {len(logs)} 条未处理 rob 日志")
    print(f"成功配对 {len(pairs)} 组，共 {len(pairs)*2} 条")
    print(f"无法配对 {len(failed)} 条")

    if failed:
        print("\n无法配对的日志：")
        for log in failed:
            print(dict(log))

    print("\n前10组配对结果：")
    for a,b in pairs[:10]:
        result="成功" if a["change_type"]=="+" else "失败"
        print(f'{a["id"]}: {a["user_id"]} -> {a["related_user_id"]}，抢劫{result}')

    if DRY_RUN:
        print("\nDRY_RUN=True，没有修改数据库")
        conn.close()
        return

    try:
        cursor.execute("BEGIN")
        for initiator,target in pairs:
            cursor.execute("UPDATE logs SET detail='initiator' WHERE id=?",(initiator["id"],))
            cursor.execute("UPDATE logs SET detail='target' WHERE id=?",(target["id"],))
        conn.commit()
        print(f"\n迁移完成，共修改 {len(pairs)*2} 条日志")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__=="__main__":
    migrate()