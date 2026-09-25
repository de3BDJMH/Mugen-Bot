import sqlite3
import math
import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DB_PATH=Path(r"D:\Nonebot\server\data\checkin\data\checkin.db")
USER_ID=3555841138#改成要测试的QQ号

def data_to_bytes(base,addition,zero):
    if base is None or addition is None:
        return None
    if zero:
        return 0
    return 2**(base+addition)

def data_rating(data_bytes):
    if data_bytes<=0:
        return 0
    mb=data_bytes/(1024**2)
    return 2.7*math.log2(1+mb/128)/math.log2(9)

def day_activity(n):
    if n<=0:
        return 0
    return 1+0.08*math.log2(n)

def b200_rating(day_scores):
    scores=sorted(day_scores.values(),reverse=True)[:200]
    return 0.51*sum(score*0.97**i for i,score in enumerate(scores))

def r30_rating(day_scores,today):
    return 0.064*sum(day_scores.get(today-datetime.timedelta(days=i+1),0)*0.95**i for i in range(30))

def get_rating(day_scores,data_bytes,today):
    b200=b200_rating(day_scores)
    r30=r30_rating(day_scores,today)
    data=data_rating(data_bytes)
    return b200+r30+data,b200,r30,data

def is_active(log):
    return (log["operation"]=="rob" and log["detail"]!="target") or log["operation"] in ["gacha","checkin"]

conn=sqlite3.connect(DB_PATH)
user=conn.execute("""
    SELECT nickname,data_base,data_addition,data_zero
    FROM users
    WHERE user_id=?
""",(USER_ID,)).fetchone()

if user is None:
    conn.close()
    raise ValueError("找不到这个用户")

rows=conn.execute("""
    SELECT id,operation,detail,change_type,data_base,data_addition,data_zero,created_at
    FROM logs
    WHERE user_id=?
    ORDER BY created_at ASC,id ASC
""",(USER_ID,)).fetchall()
conn.close()

nickname=user[0]
current_data=data_to_bytes(user[1],user[2],user[3])

logs=[]
for row in rows:
    time=datetime.datetime.fromisoformat(row[7])
    if time.tzinfo is not None:
        time=time.replace(tzinfo=None)
    logs.append({
        "id":row[0],
        "operation":row[1],
        "detail":row[2],
        "type":row[3],
        "data":data_to_bytes(row[4],row[5],row[6]),
        "time":time
    })

#从当前Data倒推日志开始时的Data
start_data=current_data
for log in reversed(logs):
    if log["data"] is None:
        continue
    if log["type"]=="+":
        start_data-=log["data"]
    elif log["type"]=="-":
        start_data+=log["data"]

if start_data<0:
    print(f"警告：逆推得到的初始Data为负数（{start_data:.2f}B），说明现有日志无法完整还原Data历史")
    start_data=0

print(f"用户: {nickname} ({USER_ID})")
print(f"当前Data: {current_data/(1024**2):.2f}MB")
print(f"逆推日志起点Data: {start_data/(1024**2):.2f}MB")
print(f"日志数量: {len(logs)}")

if not logs:
    raise ValueError("这个用户没有日志")

events={}
for log in logs:
    events.setdefault(log["time"].date(),[]).append(log)

start_date=logs[0]["time"].date()
end_date=datetime.datetime.now().date()

data=start_data
day_counts={}
day_scores={}
points=[]

def add_point(time,event):
    rating,b200,r30,data_rt=get_rating(day_scores,data,time.date())
    points.append({
        "time":time,
        "rating":rating,
        "b200":b200,
        "r30":r30,
        "data":data_rt,
        "event":event
    })

day=start_date
while day<=end_date:
    #每天0点记录一次，用于体现R30自然变化
    add_point(datetime.datetime.combine(day,datetime.time.min),"day_change")

    for log in events.get(day,[]):
        #先应用本次Data变化
        if log["data"] is not None:
            if log["type"]=="+":
                data+=log["data"]
            elif log["type"]=="-":
                data=max(0,data-log["data"])

        #再更新当日行为BP
        if is_active(log):
            day_counts[day]=day_counts.get(day,0)+1
            day_scores[day]=day_activity(day_counts[day])

        #记录本次行为后的RT
        if is_active(log) or log["data"] is not None:
            add_point(log["time"],log["operation"])

    day+=datetime.timedelta(days=1)

#验证正向重放后的Data是否与数据库当前值一致
diff=data-current_data
print(f"重放结束Data误差: {diff:.2f}B")
print(f"当前模拟RT: {points[-1]['rating']:.2f}")
print(f"B200: {points[-1]['b200']:.2f}")
print(f"R30: {points[-1]['r30']:.2f}")
print(f"DataRT: {points[-1]['data']:.2f}")

times=[p["time"] for p in points]
ratings=[p["rating"] for p in points]

fig,ax=plt.subplots(figsize=(14,6))
ax.plot(times,ratings,linewidth=1.2)
ax.set_title(f"{nickname} - Rating History")
ax.set_xlabel("Time")
ax.set_ylabel("RT")
ax.grid(alpha=0.25)

locator=mdates.AutoDateLocator()
ax.xaxis.set_major_locator(locator)
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

plt.tight_layout()
plt.show()