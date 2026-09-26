import sqlite3,json,requests,time,copy

DB_PATH=r"D:\Nonebot\server\data\log\logs.db"
BASE_URL="http://127.0.0.1:3000"
TOKEN=""
DRY_RUN=False

headers={"Content-Type":"application/json"}
if TOKEN:
    headers["Authorization"]=f"Bearer {TOKEN}"

cache={}
resolving=set()

def get_forward(forward_id:str):
    if forward_id in cache:
        return copy.deepcopy(cache[forward_id])
    if forward_id in resolving:
        return None

    resolving.add(forward_id)
    try:
        r=requests.post(f"{BASE_URL}/get_forward_msg",headers=headers,json={"id":forward_id},timeout=15)
        if r.status_code!=200:
            raise Exception(f"HTTP {r.status_code}: {r.text}")

        result=r.json()
        if result.get("status")!="ok" or result.get("retcode")!=0:
            raise Exception(str(result))

        content=result["data"]
        cache[forward_id]=content
        time.sleep(0.2)
        return copy.deepcopy(content)
    finally:
        resolving.discard(forward_id)

def repair_forward(data,row_id:int):
    success=0
    failed=0
    changed=False

    if isinstance(data,list):
        for item in data:
            c,s,f=repair_forward(item,row_id)
            changed|=c
            success+=s
            failed+=f
        return changed,success,failed

    if not isinstance(data,dict):
        return False,0,0

    if data.get("type")=="forward":
        seg_data=data.get("data",{})
        forward_id=seg_data.get("id")

        if forward_id and "content" not in seg_data:
            try:
                content=get_forward(forward_id)
                if content is not None:
                    seg_data["content"]=content
                    changed=True
                    success+=1
                    print(f"[成功] row_id={row_id} forward_id={forward_id}")
            except Exception as e:
                failed+=1
                print(f"[失败] row_id={row_id} forward_id={forward_id} {e}")

        # 无论content是以前修好的还是刚补的，都继续检查内部嵌套转发
        if "content" in seg_data:
            c,s,f=repair_forward(seg_data["content"],row_id)
            changed|=c
            success+=s
            failed+=f

        return changed,success,failed

    for value in data.values():
        c,s,f=repair_forward(value,row_id)
        changed|=c
        success+=s
        failed+=f

    return changed,success,failed

conn=sqlite3.connect(DB_PATH)
conn.row_factory=sqlite3.Row

rows=conn.execute("""
    SELECT id,message_json
    FROM messages
    WHERE message_json LIKE '%"type":"forward"%'
    ORDER BY id
""").fetchall()

success=0
failed=0
changed_rows=0

for row in rows:
    try:
        message_data=json.loads(row["message_json"])
    except Exception as e:
        print(f"[JSON错误] row_id={row['id']} {e}")
        failed+=1
        continue

    changed,s,f=repair_forward(message_data,row["id"])
    success+=s
    failed+=f

    if changed:
        changed_rows+=1
        if not DRY_RUN:
            message_json=json.dumps(message_data,ensure_ascii=False,separators=(",",":"))
            conn.execute("UPDATE messages SET message_json=? WHERE id=?",(message_json,row["id"]))

if not DRY_RUN:
    conn.commit()

print()
print(f"扫描消息数: {len(rows)}")
print(f"补全成功: {success}")
print(f"补全失败: {failed}")
print(f"修改消息数: {changed_rows}")
print(f"DRY_RUN={DRY_RUN}")

conn.close()