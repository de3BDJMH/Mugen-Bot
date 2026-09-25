import csv
import math
import sqlite3
import datetime
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

#配置
DB_PATH=Path(__file__).resolve().parents[2]/"data"/"checkin"/"data"/"checkin.db"
OUTPUT_PATH=Path(r"D:\Nonebot\server\src\services\data_race.csv")

EXCLUDE_USER_IDS={
    3827883227
    #123456789,#不希望出现在视频中的账号
}

DAYS=None#最近30天；None表示全部可用日志
STEP_HOURS=24#每3小时取一个时间点，改成1可以保留更多变化
MAX_USERS=None#None表示所有用户，也可以设为30
VALUE_MODE="MB"#MB：实际Data；EXP：log2(Data字节数)，仅用于视觉展示
MIN_PEAK_MB=100
MIN_PEAK_BYTES=MIN_PEAK_MB*(1024**2)

TZ=ZoneInfo("Asia/Shanghai")


def parse_time(value:str)->datetime.datetime:
    t=datetime.datetime.fromisoformat(value)
    if t.tzinfo is None:
        return t.replace(tzinfo=TZ)
    return t.astimezone(TZ)


def data_to_bytes(base,addition,zero)->int|None:
    if base is None or addition is None:
        return None
    if zero:
        return 0
    return int(2**(base+addition))


def display_data(value:int)->str:
    if value<=0:
        return "0B"
    for unit,size in [("PB",1024**5),("TB",1024**4),("GB",1024**3),("MB",1024**2),("KB",1024)]:
        if value>=size:
            return f"{value/size:.2f}{unit}"
    return f"{value}B"


def clean_name(value)->str:
    name=" ".join(str(value or "未知用户").split())
    name="".join(ch for ch in name if unicodedata.category(ch)!="Cf")
    return name[:20] or "未知用户"


def csv_value(value:int)->str:
    return f"{value/(1024**2):.6f}"


def load_database():
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"找不到数据库：{DB_PATH}")

    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row

    try:
        conn.execute("BEGIN")

        users=conn.execute("""
            SELECT user_id,nickname,data_base,data_addition,data_zero
            FROM users
        """).fetchall()

        rows=conn.execute("""
            SELECT id,user_id,change_type,data_base,data_addition,data_zero,created_at
            FROM logs
            ORDER BY created_at ASC,id ASC
        """).fetchall()

        conn.commit()
    finally:
        conn.close()

    snapshot_time=datetime.datetime.now(TZ)

    states={}
    for user in users:
        uid=user["user_id"]
        if uid in EXCLUDE_USER_IDS:
            continue

        current=data_to_bytes(user["data_base"],user["data_addition"],user["data_zero"])
        states[uid]={
            "name":clean_name(user["nickname"]),
            "current":current,
            "initial":0,
            "amount":0,
            "peak":0,
            "net_change":0,
            "visible":False
        }

    logs=[]
    for row in rows:
        uid=row["user_id"]
        if uid not in states:
            continue

        time=parse_time(row["created_at"])
        if time>snapshot_time:
            continue

        amount=data_to_bytes(row["data_base"],row["data_addition"],row["data_zero"])
        change=0
        if amount is not None:
            if row["change_type"]=="+":
                change=amount
            elif row["change_type"]=="-":
                change=-amount

        states[uid]["net_change"]+=change
        logs.append({
            "id":row["id"],
            "uid":uid,
            "time":time,
            "change":change
        })

    logs.sort(key=lambda x:(x["time"],x["id"]))

    #先逆推日志起点余额
    invalid=set()
    for uid,state in states.items():
        initial=state["current"]-state["net_change"]
        tolerance=max(1,state["current"]*1e-10)

        if initial<-tolerance:
            print(f"警告：用户 {uid} 逆推出负数余额，暂时排除")
            invalid.add(uid)
            continue

        initial=max(0,initial)
        state["initial"]=initial
        state["amount"]=initial
        state["peak"]=initial
        state["visible"]=initial>0

    for uid in invalid:
        del states[uid]

    logs=[log for log in logs if log["uid"] in states]

    #完整重放一次，只为了统计“历史峰值Data”
    for log in logs:
        state=states[log["uid"]]
        state["amount"]=max(0,state["amount"]+log["change"])
        if state["amount"]>state["peak"]:
            state["peak"]=state["amount"]
        if state["amount"]>0:
            state["visible"]=True

    #过滤：历史峰值从没到过50MB的用户
    low_peak={uid for uid,state in states.items() if state["peak"]<MIN_PEAK_BYTES}
    if low_peak:
        print(f"历史峰值不足{MIN_PEAK_MB}MB，被过滤：{len(low_peak)}人")
    for uid in low_peak:
        del states[uid]

    logs=[log for log in logs if log["uid"] in states]

    #重名处理
    used_names=set()
    for state in states.values():
        name=state["name"]
        candidate=name
        i=2
        while candidate in used_names:
            candidate=f"{name} #{i}"
            i+=1
        state["name"]=candidate
        used_names.add(candidate)

    #重置回日志起点状态，给后面的make_snapshots用
    for state in states.values():
        state["amount"]=state["initial"]
        state["visible"]=state["initial"]>0

    print(f"参与用户：{len(states)}")
    print(f"排除名单：{len(EXCLUDE_USER_IDS)}")
    print(f"读取日志：{len(logs)}")

    return states,logs,snapshot_time


def make_snapshots(states,logs,now):
    if not logs:
        raise ValueError("没有可用于重建Data历史的日志")

    first=logs[0]["time"]
    start=first.replace(hour=0,minute=0,second=0,microsecond=0)

    if DAYS is not None:
        cutoff=now-datetime.timedelta(days=DAYS)
        start=max(start,cutoff.replace(minute=0,second=0,microsecond=0))

    if STEP_HOURS<=0:
        raise ValueError("STEP_HOURS必须大于0")

    snapshots=[]
    index=0
    t=start

    def apply_log(log):
        state=states[log["uid"]]
        new_amount=state["amount"]+log["change"]

        if new_amount<0:
            print(f"警告：用户 {log['uid']} 在 {log['time']} 出现负数余额，已按0处理")
            new_amount=0

        state["amount"]=new_amount
        state["visible"]=True

    def save_snapshot(time):
        amounts={
            uid:state["amount"] if state["visible"] else 0
            for uid,state in states.items()
        }
        snapshots.append((time,amounts))

    #逐条处理日志，但按照设置的时间间隔保存数据
    while t<=now:
        while index<len(logs) and logs[index]["time"]<=t:
            apply_log(logs[index])
            index+=1

        save_snapshot(t)
        t+=datetime.timedelta(hours=STEP_HOURS)

    #补上当前时刻，避免最后不足一个采样间隔的变化被遗漏
    while index<len(logs) and logs[index]["time"]<=now:
        apply_log(logs[index])
        index+=1

    if snapshots[-1][0]!=now:
        save_snapshot(now)

    print(f"采样时间点：{len(snapshots)}")
    print(f"时间范围：{snapshots[0][0]} → {snapshots[-1][0]}")

    return snapshots


def export_csv(states,snapshots):
    #如果设置了MAX_USERS，就选取最后一帧Data最高的用户
    final=snapshots[-1][1]
    user_ids=sorted(states,key=lambda uid:(-final[uid],uid))

    if MAX_USERS is not None:
        user_ids=user_ids[:MAX_USERS]

    #Benri Lab：第一行时间，第一列名称
    times=[time.strftime("%Y-%m-%d %H:%M") for time,_ in snapshots]

    with open(OUTPUT_PATH,"w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(["Item\\Time",*times])

        for uid in user_ids:
            row=[states[uid]["name"]]
            row.extend(csv_value(amounts[uid]) for _,amounts in snapshots)
            writer.writerow(row)

    print(f"\nCSV已生成：{OUTPUT_PATH.resolve()}")
    print(f"CSV用户数：{len(user_ids)}")
    print(f"CSV时间点：{len(snapshots)}")

    print("\n最后一个时间点的Data排名：")
    for rank,uid in enumerate(user_ids[:10],1):
        print(f"{rank}. {states[uid]['name']}：{display_data(final[uid])}")

import re
import csv
from io import BytesIO
from urllib.request import Request,urlopen
from PIL import Image,ImageOps

AVATAR_DIR=Path(__file__).with_name("data_race_avatars")
AVATAR_LIMIT=None#第一次测试可填2，确认成功后改回None

def prepare_avatar_names(states):
    """统一CSV昵称和头像文件名"""
    used=set()

    for uid,state in states.items():
        name=str(state["name"] or "").strip()
        name=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",name)
        name=name.rstrip(" .")

        if not name:
            name=f"user_{uid}"

        if name.upper() in {"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(1,10)),*(f"LPT{i}" for i in range(1,10))}:
            name=f"_{name}"

        original=name
        n=2
        while name.casefold() in used:
            name=f"{original}_{n}"
            n+=1

        state["name"]=name
        used.add(name.casefold())

def export_avatars(states,snapshots):
    """下载参与CSV排名的用户头像，文件名与CSV昵称保持一致"""
    AVATAR_DIR.mkdir(parents=True,exist_ok=True)

    final=snapshots[-1][1]
    user_ids=sorted(states,key=lambda uid:(-final[uid],uid))
    if MAX_USERS is not None:
        user_ids=user_ids[:MAX_USERS]
    if AVATAR_LIMIT is not None:
        user_ids=user_ids[:AVATAR_LIMIT]

    success=0
    failed=[]

    with open(AVATAR_DIR/"头像对应表.csv","w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(["user_id","CSV昵称","头像文件名"])

        for i,uid in enumerate(user_ids,1):
            name=states[uid]["name"]
            filename=f"{name}.png"
            path=AVATAR_DIR/filename
            writer.writerow([uid,name,filename])

            if path.exists():
                success+=1
                print(f"[{i}/{len(user_ids)}] 已存在：{filename}")
                continue

            url=f"https://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"

            try:
                request=Request(url,headers={"User-Agent":"Mozilla/5.0"})
                with urlopen(request,timeout=15) as response:
                    content=response.read()

                with Image.open(BytesIO(content)) as image:
                    avatar=ImageOps.fit(image.convert("RGB"),(160,160),method=Image.Resampling.LANCZOS)
                    avatar.save(path,"PNG",optimize=True)

                success+=1
                print(f"[{i}/{len(user_ids)}] 下载成功：{filename}")

            except Exception as e:
                failed.append((uid,name,str(e)))
                print(f"[{i}/{len(user_ids)}] 下载失败：{name}，{e}")

    print(f"\n头像准备完成：{success}/{len(user_ids)}")
    print(f"头像目录：{AVATAR_DIR.resolve()}")

    if failed:
        print("\n下载失败的用户：")
        for uid,name,error in failed:
            print(f"{uid} {name}：{error}")

def main():
    states,logs,now=load_database()
    snapshots=make_snapshots(states,logs,now)
    prepare_avatar_names(states)
    export_csv(states,snapshots)
    export_avatars(states,snapshots)

if __name__=="__main__":
    main()