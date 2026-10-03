import sqlite3
import requests
import json
import pathlib

ROOT_PATH=pathlib.Path(__file__).parent.parent.parent
DB_PATH=ROOT_PATH/"data"/"log"/"logs.db"

BASE_URL="http://127.0.0.1:3000"
TOKEN=""
COUNT=200

conn=sqlite3.connect(DB_PATH)
conn.row_factory=sqlite3.Row

session=requests.Session()
session.headers.update({"Authorization":f"Bearer {TOKEN}"})

group_ids=[
    row["group_id"] for row in conn.execute(
        "SELECT DISTINCT group_id FROM messages WHERE group_id IS NOT NULL"
    ).fetchall()
]
group_ids=[837222085]

total_updated=0
total_matched=0
total_failed=0
total_forward=0

for group_index,group_id in enumerate(group_ids,1):
    rows=conn.execute(
        "SELECT id,message_id,time,message_json FROM messages WHERE group_id=? ORDER BY time",
        (group_id,)
    ).fetchall()

    if not rows:
        continue

    db_messages={row["message_id"]:row for row in rows}
    min_time=rows[0]["time"]

    seq=0
    updated=0
    matched=0
    failed=0
    skipped_forward=0

    print(f"\n[{group_index}/{len(group_ids)}] 开始处理群 {group_id}，数据库消息 {len(rows)} 条")

    while True:
        try:
            r=session.post(
                BASE_URL+"/get_group_msg_history",
                json={
                    "group_id":group_id,
                    "message_seq":seq,
                    "count":COUNT,
                    "reverseOrder":False
                },
                timeout=20
            )
            data=r.json()
            messages=data.get("data",{}).get("messages",[])
        except Exception as e:
            failed+=1
            print("获取失败:",e)
            break

        if not messages:
            break

        for msg in messages:
            row=db_messages.get(msg.get("message_id"))
            if row is None:
                continue

            matched+=1

            remote_message=msg.get("message",[])
            old_message=json.loads(row["message_json"])

            if old_message==remote_message:
                continue

            if any(seg.get("type")=="forward" for seg in old_message+remote_message):
                skipped_forward+=1
                continue

            conn.execute(
                "UPDATE messages SET message_json=? WHERE id=?",
                (json.dumps(remote_message,ensure_ascii=False,separators=(",",":")),row["id"])
            )
            updated+=1

        conn.commit()

        times=[msg["time"] for msg in messages if msg.get("time")]
        seqs=[int(msg["message_seq"]) for msg in messages if msg.get("message_seq") is not None]

        if times and min(times)<=min_time:
            break
        if not seqs:
            break

        next_seq=min(seqs)-1
        if next_seq<=0 or (seq>0 and next_seq>=seq):
            break

        seq=next_seq

    total_updated+=updated
    total_matched+=matched
    total_failed+=failed
    total_forward+=skipped_forward

    print(f"完成：匹配 {matched}，修复 {updated}，跳过forward {skipped_forward}，失败 {failed}")

print("\n全部完成")
print("群数量:",len(group_ids))
print("匹配:",total_matched)
print("修复:",total_updated)
print("跳过forward:",total_forward)
print("失败:",total_failed)

conn.close()