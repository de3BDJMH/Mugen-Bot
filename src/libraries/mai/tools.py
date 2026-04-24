import json
from enum import Enum
import requests
from requests.exceptions import RequestException
import matplotlib.pyplot as plt
import numpy as np
import pathlib

ALIAS=["mai","maimai"]
COMMAND_START=["","/","!","#","杠"]
ALIASES_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"mai"/"alias.json"
SONGS_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"mai"/"songs.json"
INFO_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"mai"/"info.json"
QUERY_STATE=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"mai"/"query_info.json"

RECORD_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"mai"/"records"

DEVELOPERTOKEN_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent/"data"/"mai"/"DeveloperToken.txt"

RANKLENGTH=200

def id2songName(id):
    """ID转标准曲名"""
    with open(SONGS_PATH,encoding="utf-8") as f:
        info=json.load(f)
    return info[id]

def alias2id(alia):
    """别名转ID"""
    with open(ALIASES_PATH,encoding="utf-8") as f:
        aliases=json.load(f)
    ids=[]
    for id in aliases.keys():
        for a in aliases[id]:
            if a.lower()==alia.lower():
                ids.append(id)
                continue
    if ids:
        return ids
    return None

def get_developer_token():
    with open(DEVELOPERTOKEN_PATH, "r", encoding="utf-8") as f:
        token = f.read().strip()
    return token

def update(qq):
    headers={
        "Developer-Token": get_developer_token()
    }
    url=f"https://www.diving-fish.com/api/maimaidxprober/dev/player/records?qq={qq}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        path=RECORD_PATH/f"{qq}record.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=4)
        return True
    else:
        return False
    
def get_rating(qq):
    url=f"https://www.diving-fish.com/api/maimaidxprober/query/player"
    response = requests.post(url, json={"qq": qq, "b50": "1"})
    if response.status_code == 200:
        data=response.json()
        return data["rating"]
    else:
        return None

class FiNALEType(Enum):
    A="A"
    FC="FC"
    SSS="SSS"
    AP="AP"
    FDX="FDX"

class ALLPERFECTType(Enum):
    A="A"
    FC="FC"
    SSS="SSS"
    AP="AP"
    FDX="FDX"

FiNALEVER={
    "maimai PLUS":"真",
    "maimai GreeN":"超",
    "maimai GreeN PLUS":"檄",
    "maimai ORANGE":"橙",
    "maimai ORANGE PLUS":"哓",
    "maimai PiNK":"桃",
    "maimai PiNK PLUS":"樱",
    "maimai MURASAKi":"紫",
    "maimai MURASAKi PLUS":"堇",
    "maimai MiLK":"白",
    "MiLK PLUS":"雪",
    "maimai FiNALE":"辉"
}
VER={
    "maimai PLUS":"真",
    "maimai GreeN":"超",
    "maimai GreeN PLUS":"檄",
    "maimai ORANGE":"橙",
    "maimai ORANGE PLUS":"哓",
    "maimai PiNK":"桃",
    "maimai PiNK PLUS":"樱",
    "maimai MURASAKi":"紫",
    "maimai MURASAKi PLUS":"堇",
    "maimai MiLK":"白",
    "MiLK PLUS":"雪",
    "maimai FiNALE":"辉",
    "maimai でらっくす":"熊华",
    "maimai でらっくす Splash":"爽煌",
    "maimai でらっくす UNiVERSE":"宙星",
    "maimai でらっくす FESTiVAL":"祭祝",
    "maimai でらっくす BUDDiES":"双宴",
    "maimai でらっくす PRiSM":"镜",
}

QUERY_COOLDOWN=10*60
RANK_QUERY_COOLDOWN=2*60*60

def get_records(query_type,qq):
    COLOR={0:"绿",1:"黄",2:"红",3:"紫",4:"白"}
    DELETE_ID=[(47, 4), (85, 4), (111, 4), (115, 4), (131, 4), (133, 4), (134, 4), (144, 4), (155, 4), (219, 4), (239, 4), (240, 4), (248, 4), (252, 4), (260, 4), (261, 4), (328, 4), (364, 4), (367, 4), (378, 4), (389, 4), (463, 4), (464, 4), (472, 4), (629, 4), (704, 4), (382, 0), (382, 1), (382, 2), (382, 3), (711, 0), (711, 1), (711, 2), (711, 3), (853, 0), (853, 1), (853, 2), (853, 3), (341, 0), (341, 1), (341, 2), (341, 3), (451, 0), (451, 1), (451, 2), (451, 3), (455, 0), (455, 1), (455, 2), (455, 3), (460, 0), (460, 1), (460, 2), (460, 3), (792, 0), (792, 1), (792, 2), (792, 3), (792, 4), (1020, 0), (1020, 1), (1020, 2), (1020, 3), (1051, 0), (1051, 1), (1051, 2), (1051, 3), (1085, 0), (1085, 1), (1085, 2), (1085, 3), (1081, 0), (1081, 1), (1081, 2), (1081, 3), (1301, 0), (1301, 1), (1301, 2), (1301, 3), (146, 0), (146, 1), (146, 2), (146, 3), (146, 4), (189, 0), (189, 1), (189, 2), (189, 3), (419, 0), (419, 1), (419, 2), (419, 3), (687, 0), (687, 1), (687, 2), (687, 3), (688, 0), (688, 1), (688, 2), (688, 3), (712, 0), (712, 1), (712, 2), (712, 3), (731, 0), (731, 1), (731, 2), (731, 3), (731, 4), (1235, 0), (1235, 1), (1235, 2), (1235, 3), (185, 0), (185, 1), (185, 2), (185, 3), (524, 0), (524, 1), (524, 2), (524, 3), (1103, 0), (1103, 1), (1103, 2), (1103, 3), (44, 0), (44, 1), (44, 2), (44, 3)]
    DELETE_ID=[(47, 4), (85, 4), (111, 4), (115, 4), (131, 4), (133, 4), (134, 4), (144, 4), (155, 4), (219, 4), (239, 4), (240, 4), (248, 4), (252, 4), (260, 4), (261, 4), (328, 4), (364, 4), (367, 4), (378, 4), (389, 4), (463, 4), (464, 4), (472, 4), (629, 4), (704, 4), (711, 0), (711, 1), (711, 2), (711, 3), (853, 0), (853, 1), (853, 2), (853, 3), (341, 0), (341, 1), (341, 2), (341, 3), (451, 0), (451, 1), (451, 2), (451, 3), (455, 0), (455, 1), (455, 2), (455, 3), (460, 0), (460, 1), (460, 2), (460, 3), (792, 0), (792, 1), (792, 2), (792, 3), (792, 4), (1020, 0), (1020, 1), (1020, 2), (1020, 3), (1051, 0), (1051, 1), (1051, 2), (1051, 3), (1085, 0), (1085, 1), (1085, 2), (1085, 3), (1081, 0), (1081, 1), (1081, 2), (1081, 3), (1301, 0), (1301, 1), (1301, 2), (1301, 3), (146, 0), (146, 1), (146, 2), (146, 3), (146, 4), (189, 0), (189, 1), (189, 2), (189, 3), (419, 0), (419, 1), (419, 2), (419, 3), (687, 0), (687, 1), (687, 2), (687, 3), (688, 0), (688, 1), (688, 2), (688, 3), (712, 0), (712, 1), (712, 2), (712, 3), (731, 0), (731, 1), (731, 2), (731, 3), (731, 4), (1235, 0), (1235, 1), (1235, 2), (1235, 3), (185, 0), (185, 1), (185, 2), (185, 3), (524, 0), (524, 1), (524, 2), (524, 3), (1103, 0), (1103, 1), (1103, 2), (1103, 3), (44, 0), (44, 1), (44, 2), (44, 3)]
    ###注：第二行删除了歌曲《おこちゃま戦争》ID382，为橙代的一首歌，该歌曲谱面cid均不属于旧框体，但是橙系列牌子都要求打这首歌，原因未知，但是按照标准这首舞系列牌子也需要打，所以先删除了

    #统计数据
    with open(INFO_PATH,encoding='utf-8') as f:
        info=json.load(f)
    with open(RECORD_PATH/f"{qq}record.json",encoding='utf-8') as f:
        records=json.load(f)
        records=records["records"]
    clear_id=[]
    if type(query_type)==FiNALEType:
        V=FiNALEVER
        for song in records:
            if song["song_id"]>=10000 or (song["song_id"],song["level_index"]) in DELETE_ID:
                continue
            if query_type==FiNALEType.A:
                if song["achievements"]>=80:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==FiNALEType.FC:
                if song["fc"]:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==FiNALEType.SSS:
                if song["rate"] in ["sss","sssp"]:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==FiNALEType.AP:
                if song["fc"] in ["ap","app"]:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==FiNALEType.FDX:
                if song["fs"] in ["fsd","fsdp"]:
                    clear_id.append([song["song_id"],song["level_index"]])
    elif type(query_type)==ALLPERFECTType:
        V=VER
        for song in records:
            if song["song_id"]>=100000:
                continue
            if query_type==ALLPERFECTType.A:
                if song["achievements"]>=80:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==ALLPERFECTType.FC:
                if song["fc"]:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==ALLPERFECTType.SSS:
                if song["rate"] in ["sss","sssp"]:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==ALLPERFECTType.AP:
                if song["fc"] in ["ap","app"]:
                    clear_id.append([song["song_id"],song["level_index"]])
            elif query_type==ALLPERFECTType.FDX:
                if song["fs"] in ["fsd","fsdp"]:
                    clear_id.append([song["song_id"],song["level_index"]])
    difs={}
    cleared_difs={}
    vers={}
    cleared_vers={}
    if type(query_type)==FiNALEType:
        for s in info:
            for color in range(len(s["level"])):
                if int(s["id"])>=10000 or (int(s["id"]),color) in DELETE_ID:
                    continue
                if s["level"][color] not in difs:
                    difs[s["level"][color]]={"Clear":0,"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                    cleared_difs[s["level"][color]]={"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                if [int(s["id"]),color] in clear_id:
                    difs[s["level"][color]]["Clear"]+=1
                    cleared_difs[s["level"][color]][COLOR[color]]+=1
                else:
                    difs[s["level"][color]][COLOR[color]]+=1
                v=s["basic_info"]["from"]
                if v=="maimai":
                    v="maimai PLUS"
                if v not in vers:
                    vers[v]={"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                    cleared_vers[v]={"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                if [int(s["id"]),color] in clear_id:
                    cleared_vers[v][COLOR[color]]+=1
                else:
                    vers[v][COLOR[color]]+=1
    elif type(query_type)==ALLPERFECTType:
        for s in info:
            for color in range(len(s["level"])):
                if int(s["id"])>=100000:
                    continue
                if s["level"][color] not in difs:
                    difs[s["level"][color]]={"Clear":0,"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                    cleared_difs[s["level"][color]]={"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                if [int(s["id"]),color] in clear_id:
                    difs[s["level"][color]]["Clear"]+=1
                    cleared_difs[s["level"][color]][COLOR[color]]+=1
                else:
                    difs[s["level"][color]][COLOR[color]]+=1
                v=s["basic_info"]["from"]
                if v=="maimai":
                    v="maimai PLUS"
                if v not in vers:
                    vers[v]={"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                    cleared_vers[v]={"绿":0,"黄":0,"红":0,"紫":0,"白":0}
                if [int(s["id"]),color] in clear_id:
                    cleared_vers[v][COLOR[color]]+=1
                else:
                    vers[v][COLOR[color]]+=1
    #整理数据
    sorted_difs=[]
    sorted_difs_keys=[]
    sorted_cleared_difs=[]
    for k in range(1,16):
        if str(k) in difs:
            sorted_difs+=[list(difs[str(k)].values())]
            sorted_cleared_difs+=[list(cleared_difs[str(k)].values())]
            sorted_difs_keys+=[str(k)]
        if str(k)+"+" in difs:
            sorted_difs+=[list(difs[str(k)+"+"].values())]
            sorted_cleared_difs+=[list(cleared_difs[str(k)+"+"].values())]
            sorted_difs_keys+=[str(k)+"+"]
    sorted_vers=[]
    sorted_cleared_vers=[]
    for v in V:
        sorted_vers+=[list(vers[v].values())]
        sorted_cleared_vers+=[list(cleared_vers[v].values())]
    
    return sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers

def paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path):
    path=str(path)
    # 设置字体为SimHei（黑体）
    plt.rcParams['font.sans-serif'] = ['SimHei']
    # 解决坐标轴负号显示问题
    plt.rcParams['axes.unicode_minus'] = False

    if path[-5]=="a" and path[-7:-4]!="dxa":
        ptype="霸者"
    elif path[-6:-4]=="fc" and path[-8:-4]!="dxfc":
        ptype="舞极"
    elif path[-7:-4]=="sss" and path[-9:-4]!="dxsss":
        ptype="舞将"
    elif path[-6:-4]=="ap" and path[-8:-4]!="dxap":
        ptype="舞神"
    elif path[-7:-4]=="fdx" and path[-9:-4]!="dxfdx":
        ptype="舞舞舞"
    elif path[-7:-4]=="dxa":
        ptype="DX霸者"
    elif path[-8:-4]=="dxfc":
        ptype="DX舞极"
    elif path[-9:-4]=="dxsss":
        ptype="DX舞将"
    elif path[-8:-4]=="dxap":
        ptype="DX舞神"
    elif path[-9:-4]=="dxfdx":
        ptype="DX舞舞舞"
    if "DX" in ptype:
        V=VER
    else:
        V=FiNALEVER

    #绘图
    fig, axs = plt.subplots(nrows=2, ncols=1)
    if "DX" in ptype:
        axs[0].figure.set_figwidth(20)
        axs[0].figure.set_figheight(9)
        textp=8
        texts=8
    else:
        axs[0].figure.set_figwidth(15)
        axs[0].figure.set_figheight(7)
        textp=5
        texts=10
    width=0.5
    x=np.arange(len(sorted_difs_keys))
    #按难度绘制
    axs[0].bar(x,[n[0] for n in sorted_difs],width,label="Cleared",color="#DCDCDC")
    axs[0].bar(x,[n[1] for n in sorted_difs],width,label=f"{sum([n[1] for n in sorted_difs])}/{sum([n[1] for n in sorted_difs])+sum([n[0] for n in sorted_cleared_difs])}  {round(sum([n[1] for n in sorted_difs])/(sum([n[1] for n in sorted_difs])+sum([n[0] for n in sorted_cleared_difs]))*100,1)}%",color="#76EE00",bottom=[n[0] for n in sorted_difs])
    axs[0].bar(x,[n[2] for n in sorted_difs],width,label=f"{sum([n[2] for n in sorted_difs])}/{sum([n[2] for n in sorted_difs])+sum([n[1] for n in sorted_cleared_difs])}  {round(sum([n[2] for n in sorted_difs])/(sum([n[2] for n in sorted_difs])+sum([n[1] for n in sorted_cleared_difs]))*100,1)}%",color="#FFD700",bottom=[n[0]+n[1] for n in sorted_difs])
    axs[0].bar(x,[n[3] for n in sorted_difs],width,label=f"{sum([n[3] for n in sorted_difs])}/{sum([n[3] for n in sorted_difs])+sum([n[2] for n in sorted_cleared_difs])}  {round(sum([n[3] for n in sorted_difs])/(sum([n[3] for n in sorted_difs])+sum([n[2] for n in sorted_cleared_difs]))*100,1)}%",color="#FF3030",bottom=[n[0]+n[1]+n[2] for n in sorted_difs])
    axs[0].bar(x,[n[4] for n in sorted_difs],width,label=f"{sum([n[4] for n in sorted_difs])}/{sum([n[4] for n in sorted_difs])+sum([n[3] for n in sorted_cleared_difs])}  {round(sum([n[4] for n in sorted_difs])/(sum([n[4] for n in sorted_difs])+sum([n[3] for n in sorted_cleared_difs]))*100,1)}%",color="#9400D3",bottom=[n[0]+n[1]+n[2]+n[3] for n in sorted_difs])
    axs[0].bar(x,[n[5] for n in sorted_difs],width,label=f"{sum([n[5] for n in sorted_difs])}/{sum([n[5] for n in sorted_difs])+sum([n[4] for n in sorted_cleared_difs])}  {round(sum([n[5] for n in sorted_difs])/(sum([n[5] for n in sorted_difs])+sum([n[4] for n in sorted_cleared_difs]))*100,1)}%",color="#FFBBFF",bottom=[n[0]+n[1]+n[2]+n[3]+n[4] for n in sorted_difs])
    axs[0].bar_label(axs[0].containers[0], ["" if n[0]==0 else f"{n[0]}/{sum(n)}" for n in sorted_difs], padding=3)
    axs[0].bar_label(axs[0].containers[5], ["" if sum(n[1:])==0 else sum(n[1:]) for n in sorted_difs], padding=3)
    axs[0].bar_label(axs[0].containers[5], [str(round(n[0]/sum(n)*100,1))+"%" for n in sorted_difs],padding=18)
    axs[0].set_xlabel("难度")
    axs[0].set_ylabel("数量")
    axs[0].set_xticks(x,sorted_difs_keys)
    axs[0].set_ylim(0, max([sum(n) for n in sorted_difs])*1.2)
    axs[0].legend()
    #按版本绘制
    width=0.18
    x=np.arange(len(sorted_vers))
    x+=1
    axs[1].bar(x-2*width,[v[0] for v in sorted_cleared_vers],width,color="#DCDCDC")
    axs[1].bar(x-2*width,[v[0] for v in sorted_vers],width,color="#76EE00",bottom=[v[0] for v in sorted_cleared_vers])
    axs[1].bar(x-1*width,[v[1] for v in sorted_cleared_vers],width,color="#DCDCDC")
    axs[1].bar(x-1*width,[v[1] for v in sorted_vers],width,color="#FFD700",bottom=[v[1] for v in sorted_cleared_vers])
    axs[1].bar(x+0*width,[v[2] for v in sorted_cleared_vers],width,color="#DCDCDC")
    axs[1].bar(x+0*width,[v[2] for v in sorted_vers],width,color="#FF3030",bottom=[v[2] for v in sorted_cleared_vers])
    axs[1].bar(x+1*width,[v[3] for v in sorted_cleared_vers],width,color="#DCDCDC")
    axs[1].bar(x+1*width,[v[3] for v in sorted_vers],width,color="#9400D3",bottom=[v[3] for v in sorted_cleared_vers])
    axs[1].bar(x+2*width,[v[4] for v in sorted_cleared_vers],width,color="#DCDCDC")
    axs[1].bar(x+2*width,[v[4] for v in sorted_vers],width,color="#FFBBFF",bottom=[v[4] for v in sorted_cleared_vers])
    for v in range(len(sorted_vers)):
        axs[1].text(x[v]-0.45,sorted_vers[v][0]+sorted_cleared_vers[v][0]+1,f"非白谱各 {sorted_vers[v][0]+sorted_cleared_vers[v][0]}张",fontsize=8)
        axs[1].text(x[v]-0.45,sorted_vers[v][0]+sorted_cleared_vers[v][0]+1+textp,f"白谱共有 {sorted_vers[v][4]+sorted_cleared_vers[v][4]}张",fontsize=8)
        axs[1].text(x[v]-0.45,sorted_vers[v][0]+sorted_cleared_vers[v][0]+1+2*textp,f"版本进度 {round(sum(sorted_cleared_vers[v])/(sum(sorted_vers[v])+sum(sorted_cleared_vers[v]))*100,1)}%",fontsize=8)
    for c in range(5):
        axs[1].bar_label(axs[1].containers[2*c], ["" if n[c]==0 else f"{n[c]}" for n in sorted_cleared_vers], padding=-10,fontsize=texts)
        axs[1].bar_label(axs[1].containers[2*c], ["" if n[c]==0 else f"{n[c]}" for n in sorted_vers], padding=2,fontsize=texts)
    axs[1].set_ylim(0, max([sorted_vers[v][0]+sorted_cleared_vers[v][0] for v in range(len(sorted_vers))])*1.2)
    axs[1].set_xticks(x,V.values())
    axs[1].set_xlabel("版本")
    axs[1].set_ylabel("数量")
    
    axs[0].set_title(f"{ptype}进度  ({sum([n[0] for n in sorted_difs])}/{sum([sum(n) for n in sorted_difs])}  {round(sum([n[0] for n in sorted_difs])/sum([sum(n) for n in sorted_difs])*100,1)}%)",loc="left",pad=5,fontsize=18)
    plt.savefig(path)

#用于处理开字母的一些函数
def _replace(name,ch):
    res=""
    for c in name:
        if c in ch or c==" ":
            res+=c
        else:
            res+="*"
    return res

def puzzleGenerate(songs:list,ch:list,right:list,fail:list,finish:bool=False):
    """
    songs:题库
    ch:已开字符
    right:已答对的曲目
    fail:字母全被开出来的
    finish:是否为强制结束
    """
    if ch:
        res=f"已开字符：{" ".join(ch)}\n"
    elif finish:
        res="游戏已提前结束，答案如下：\n"
    else:
        res=""
    for n in range(len(songs)):
        song=songs[n]
        if song in right:
            if song in fail:
                res+=f"🟧{n+1}. {id2songName(song)}\n"
            else:
                res+=f"🟩{n+1}. {id2songName(song)}\n"
        else:
            if not finish:
                res+=f"🟥{n+1}. {_replace(id2songName(song),ch)}\n"
            else:
                res+=f"🟥{n+1}. {id2songName(song)}\n"
    return res[:-1]

def match(song,ch):
    """检测这个歌的字母是不是都被开了"""
    re_song=_replace(id2songName(song),ch)
    if re_song==id2songName(song):
        return True
    return False