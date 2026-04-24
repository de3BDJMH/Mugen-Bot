import requests
import json

songs=requests.get("https://www.diving-fish.com/api/maimaidxprober/music_data").json()#歌曲数据
with open(r"D:\LLOneBot\guess\guess\plugins\mai\info.json","w",encoding="utf-8") as f:
    json.dump(songs,f,indent=4)

data=requests.get("https://www.yuzuchan.moe/api/maimaidx"+"/maimaidxalias").json()
data=data["content"]
with open(r"D:\LLOneBot\guess\guess\plugins\mai\alias.json",encoding="utf-8") as f:
    alias = json.load(f)
for s in data:
    if str(s["SongID"]) not in alias:
        alias[str(s["SongID"])] = s["Alias"]
    else:
        for a in s["Alias"]:
            if a not in alias[str(s["SongID"])]:
                alias[str(s["SongID"])].append(a)
with open(r"D:\LLOneBot\guess\guess\plugins\mai\alias.json","w",encoding="utf-8") as f:
    json.dump(alias,f,indent=4)