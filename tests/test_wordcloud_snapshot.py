import datetime
import sys
from pathlib import Path
import requests
import time


ROOT_PATH=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT_PATH))
from src.services.wordcloud import read_snapshot
from src.services.wordcloud import write_snapshot_file
from src.services.wordcloud import load_snapshot_file
from src.api.config import load_api_config

api_key=load_api_config().mugen_internal_api_key.get_secret_value()

end=datetime.date.today()
start=end-datetime.timedelta(days=29)

snapshot=read_snapshot(start,end)

print("时间范围:",snapshot.period_start,"~",snapshot.period_end)
print("生成时间:",snapshot.generated_at)
print("有数据的日期:",len(snapshot.daily_counts))

groups=set()
words=set()
users=set()

for day,day_words in snapshot.daily_counts.items():
    groups.update(snapshot.daily_groups.get(day,set()))

    for word,per_user in day_words.items():
        words.add(word)
        users.update(per_user.keys())

print("群数量:",len(groups))
print("用户数量:",len(users))
print("不同词语:",len(words))

print("\n群ID示例:",list(groups)[:3])
print("用户ID示例:",list(users)[:3])

for day,day_words in snapshot.daily_counts.items():
    print("\n日期示例:",day)

    for word,per_user in list(day_words.items())[:5]:
        print(word,dict(per_user))

    break

write_snapshot_file(snapshot)

print("快照写入完成")

loaded=load_snapshot_file()

print("读取成功:",loaded is not None)

if loaded:
    print("时间范围:",loaded.period_start,"~",loaded.period_end)
    print("生成时间:",loaded.generated_at)
    print("有数据的日期:",len(loaded.daily_counts))
print(snapshot.daily_counts==loaded.daily_counts)
print(snapshot.daily_groups==loaded.daily_groups)

start=time.time()

response=requests.get(
    "http://127.0.0.1:8080/api/wordcloud/snapshot",
    headers={"X-Mugen-API-Key": api_key},
)

print("状态码:",response.status_code)
print("耗时:",time.time()-start)
print("响应大小:",len(response.content)/1024/1024,"MB")
print(response.text)