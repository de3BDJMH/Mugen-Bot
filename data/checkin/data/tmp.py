import json

with open("data\\checkin\\data\\tmp.json", encoding="utf-8") as f:
    data = json.load(f)
with open("data\\checkin\\data\\user.json", encoding="utf-8") as f:
    user=json.load(f)
for u in user:
    if not u in data:
        user[u]["rob"]={
        "rate": 50,
        "last_rob": "1970-01-01 00:00:00",
        "robbed": {},
        "robbed_by": []
    }
    else:
        user[u]["rob"]=data[u]["rob"]
with open("data\\checkin\\data\\user.json", "w", encoding="utf-8") as f:
    json.dump(user,f,ensure_ascii=False,indent=2)