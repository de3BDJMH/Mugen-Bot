from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.plugin import on_message

from .config import Config

import json
import random
import time
import os
import pathlib

from ...libraries.mai.tools import *
from ...libraries import command_split
from ...libraries.tools import *

__plugin_meta__ = PluginMetadata(
    name="mai",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

########################
#插件自定义设置，保证整体相关性，联通性
TAG="mai"#该插件的tag，用于指令分割

#指令设置
COMMAND_ALIAS={
    "guess":["guess","开字母","开","k","字母"],
    "霸者进度":["霸者进度"],
    "舞极进度":["舞极进度"],
    "舞将进度":["舞将进度"],
    "舞神进度":["舞神进度"],
    "舞舞舞进度":["舞舞舞进度"],
    "舞系列进度":["舞系列进度"],
    "DX霸者进度":["DX霸者进度","dx霸者进度"],
    "DX舞极进度":["DX舞极进度","dx舞极进度"],
    "DX舞将进度":["DX舞将进度","dx舞将进度"],
    "DX舞神进度":["DX舞神进度","dx舞神进度"],
    "DX舞舞舞进度":["DX舞舞舞进度","dx舞舞舞进度"],
    "DX舞系列进度":["DX舞系列进度","dx舞系列进度"],
    "rt排行":["rt排行"],
    "霸者排行":["霸者排行"],
    "DX霸者排行":["DX霸者排行"]
}#该内容已转移到libraries中，修改这里无用

HELP_KEYWORD=["help","帮助","-h","-help"]

#路径设置
ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent #/server
DATA_PATH=ROOT_PATH/"data"/"mai"

GUESS_ACCOUNT_PATH=DATA_PATH/"guess"/"account.json"#开字母账号ID信息的路径
GUESS_CONFIG_PATH=DATA_PATH/"guess"/"config.json"#开字母设置路径
GUESS_STATE_PATH=DATA_PATH/"guess"/"state.json"#开字母状态路径
GUESS_DATA_PATH=DATA_PATH/"guess"/"data.json"#开字母游戏信息路径

PROGRESS_PIC_PATH=DATA_PATH/"out"#输出图片的根目录
PROGRESS_RECORD_PATH=DATA_PATH/"records"#用户成绩的根目录

#杂项
HIRAGANA={'あ': 'ア', 'い': 'イ', 'う': 'ウ', 'え': 'エ', 'お': 'オ', 'か': 'カ', 'き': 'キ', 'く': 'ク', 'け': 'ケ', 'こ': 'コ', 'さ': 'サ', 'し': 'シ', 'す': 'ス', 'せ': 'セ', 'そ': 'ソ', 'た': 'タ', 'ち': 'チ', 'つ': 'ツ', 'て': 'テ', 'と': 'ト', 'な': 'ナ', 'に': 'ニ', 'ぬ': 'ヌ', 'ね': 'ネ', 'の': 'ノ', 'は': 'ハ', 'ひ': 'ヒ', 'ふ': 'フ', 'へ': 'ヘ', 'ほ': 'ホ', 'ま': 'マ', 'み': 'ミ', 'む': 'ム', 'め': 'メ', 'も': 'モ', 'や': 'ヤ', 'ゆ': 'ユ', 'よ': 'ヨ', 'ら': 'ラ', 'り': 'リ', 'る': 'ル', 'れ': 'レ', ' ろ': 'ロ', 'わ': 'ワ', 'を': 'ヲ', 'ん': 'ン', 'が': 'ガ', 'ぎ': 'ギ', 'ぐ': 'グ', 'げ': 'ゲ', 'ご': 'ゴ', 'ざ': 'ザ', 'じ': 'ジ', 'ず': 'ズ', 'ぜ': 'ゼ', 'ぞ': 'ゾ', 'だ': 'ダ', 'ぢ': 'ヂ', 'づ': 'ヅ', 'で': 'デ', 'ど': 'ド', 'ば': 'バ', 'び': 'ビ', 'ぶ': 'ブ', 'べ': 'ベ', 'ぼ': 'ボ', 'ぱ': 'パ', 'ぴ': 'ピ', 'ぷ': 'プ', 'ぺ': 'ペ', ' ぽ': 'ポ', 'きゃ': 'キャ', 'きゅ': 'キュ', 'きょ': 'キョ', 'ぎゃ': 'ギャ', 'ぎゅ': 'ギュ', 'ぎょ': 'ギョ', 'しゃ': 'シャ', 'しゅ': 'シュ', 'しょ': 'ショ', 'じゃ': 'ジャ', 'じゅ': 'ジュ', 'じょ': 'ジョ', 'ちゃ': 'チャ', 'ちゅ': 'チュ', 'ちょ': 'チョ', 'にゃ': 'ニャ', 'にゅ': 'ニュ', 'にょ': 'ニョ', 'ひゃ': 'ヒャ', 'ひゅ': 'ヒュ', 'ひょ': 'ヒョ', 'びゃ': 'ビャ', 'びゅ': 'ビュ', 'びょ': 'ビョ', 'ぴゃ': 'ピャ', 'ぴゅ': 'ピュ', 'ぴょ': 'ピョ', 'みゃ': 'ミャ', 'みゅ': 'ミュ', 'みょ': 'ミョ', 'りゃ': 'リャ', 'りゅ': 'リュ', 'りょ': 'リョ'}
KATAKANA={'ア': 'あ', 'イ': 'い', 'ウ': 'う', 'エ': 'え', 'オ': 'お', 'カ': 'か', 'キ': 'き', 'ク': 'く', 'ケ': 'け', 'コ': 'こ', 'サ': 'さ', 'シ': 'し', 'ス': 'す', 'セ': 'せ', 'ソ': 'そ', 'タ': 'た', 'チ': 'ち', 'ツ': 'つ', 'テ': 'て', 'ト': 'と', 'ナ': 'な', 'ニ': 'に', 'ヌ': 'ぬ', 'ネ': 'ね', 'ノ': 'の', 'ハ': 'は', 'ヒ': 'ひ', 'フ': 'ふ', 'ヘ': 'へ', 'ホ': 'ほ', 'マ': 'ま', 'ミ': 'み', 'ム': 'む', 'メ': 'め', 'モ': 'も', 'ヤ': 'や', 'ユ': 'ゆ', 'ヨ': 'よ', 'ラ': 'ら', 'リ': 'り', 'ル': 'る', 'レ': 'れ', ' ロ': 'ろ', 'ワ': 'わ', 'ヲ': 'を', 'ン': 'ん', 'ガ': 'が', 'ギ': 'ぎ', 'グ': 'ぐ', 'ゲ': 'げ', 'ゴ': 'ご', 'ザ': 'ざ', 'ジ': 'じ', 'ズ': 'ず', 'ゼ': 'ぜ', 'ゾ': 'ぞ', 'ダ': 'だ', 'ヂ': 'ぢ', 'ヅ': 'づ', 'デ': 'で', 'ド': 'ど', 'バ': 'ば', 'ビ': 'び', 'ブ': 'ぶ', 'ベ': 'べ', 'ボ': 'ぼ', 'パ': 'ぱ', 'ピ': 'ぴ', 'プ': 'ぷ', 'ペ': 'ぺ', ' ポ': 'ぽ', 'キャ': 'きゃ', 'キュ': 'きゅ', 'キョ': 'きょ', 'ギャ': 'ぎゃ', 'ギュ': 'ぎゅ', 'ギョ': 'ぎょ', 'シャ': 'しゃ', 'シュ': 'しゅ', 'ショ': 'しょ', 'ジャ': 'じゃ', 'ジュ': 'じゅ', 'ジョ': 'じょ', 'チャ': 'ちゃ', 'チュ': 'ちゅ', 'チョ': 'ちょ', 'ニャ': 'にゃ', 'ニュ': 'にゅ', 'ニョ': 'にょ', 'ヒャ': 'ひゃ', 'ヒュ': 'ひゅ', 'ヒョ': 'ひょ', 'ビャ': 'びゃ', 'ビュ': 'びゅ', 'ビョ': 'びょ', 'ピャ': 'ぴゃ', 'ピュ': 'ぴゅ', 'ピョ': 'ぴょ', 'ミャ': 'みゃ', 'ミュ': 'みゅ', 'ミョ': 'みょ', 'リャ': 'りゃ', 'リュ': 'りゅ', 'リョ': 'りょ'}
JP=list(HIRAGANA.keys())+list(KATAKANA.keys())
########################

mai = on_message()
@mai.handle()
async def maiMain(matcher:Matcher,bot:Bot,event:Event):
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    #聊天消息转指令
    recive=event.get_message()
    result=command_split.split(recive,TAG,getGroupID(event))
    if not result:
        return
    if result["state"]==False:
        msg=result["msg"]
        if result["pic"]:
            msg+=MessageSegment.image(result["pic"])
        if result["need_reply"] and msg:
            await mai.finish(msg)
        else:
            return
    arg=result["arg"]
    guess_need_reply=result["need_reply"]
    print(arg)
    if not arg:
        return
    
    #处理指令
    if arg[0]=="guess":
        user_id=event.get_user_id()
        guess_id=getGroupID(event)
        with open(GUESS_ACCOUNT_PATH,encoding="utf-8") as f:#判断用户是否存在
            accounts=json.load(f)
        if not user_id in accounts:
            user_name=await bot.call_api("get_stranger_info",user_id=user_id)
            user_name=user_name["nick"]
            accounts[user_id]=user_name
            with open(GUESS_ACCOUNT_PATH,"w",encoding="utf-8") as f:
                json.dump(accounts,f)
        with open(GUESS_DATA_PATH,encoding="utf-8") as f:
            guess_data=json.load(f)
        if not user_id in guess_data["player"]:
            guess_data["player"][user_id]={"ch":{},"right":{}}
        with open(GUESS_DATA_PATH,"w",encoding="utf-8") as f:
            json.dump(guess_data,f)
        with open(GUESS_CONFIG_PATH,encoding="utf-8") as f:#判断是否第一次游戏
            guess_config=json.load(f)
        if not guess_id in guess_config:
            guess_config[guess_id]={"n":10,"jp":False}#n为题目数量
        with open(GUESS_CONFIG_PATH,"w",encoding="utf-8") as f:
            json.dump(guess_config,f)
        if len(arg)==1 or "开始" in arg:#开始游戏
            with open(GUESS_STATE_PATH,encoding="utf-8") as f:
                guess_state=json.load(f)
                if not guess_id in guess_state:
                    guess_state[guess_id]={"start":False,"puzzle":[],"open":[],"right":[],"fail":[],"startTime":time.time()}
                elif guess_state[guess_id]["start"]:
                    await mai.finish("游戏已经开始，请提供字符或曲名")
            with open(SONGS_PATH,encoding="utf-8") as f:
                songs=json.load(f)
            songlist=[]
            if guess_config[guess_id]["jp"]:
                songlist=list(songs.keys())
            else:
                for sid in songs:
                    s=songs[sid]
                    if not any(element in s for element in JP):
                        songlist.append(sid)
            guess_songs=random.sample(songlist,guess_config[guess_id]["n"])#生成题目
            with open(GUESS_DATA_PATH,encoding="utf-8") as f:
                guess_data=json.load(f)
            for s in guess_songs:
                if not s in guess_data:
                    guess_data["total"]["ans"][s]={"right":0,"false":0,"fail":0}
            with open(GUESS_DATA_PATH,"w",encoding="utf-8") as f:
                json.dump(guess_data,f)
            guess_state[guess_id]["start"]=True
            guess_state[guess_id]["puzzle"]=guess_songs
            guess_state[guess_id]["startTime"]=time.time()
            with open(GUESS_STATE_PATH,"w",encoding="utf-8") as f:
                json.dump(guess_state,f)
            await mai.finish(puzzleGenerate(guess_songs,[],[],[]))
        else:
            if arg[1] in HELP_KEYWORD:
                await mai.finish("开字母帮助：\n/mai guess [开始]    开始游戏，开始可选\n/mai guess 结束    提前结束游戏\n/mai guess 开 <字符>    开一个字符\n/mai guess 答 <曲名>    回答\n/mai guess 设置    进行游戏参数设置\n\n注：游戏开始后开字符可以直接发送“开x”，回答也可直接发送答案，但是这种情况下bot不会回复你是别名不存在还是答错")
            elif arg[1]=="结束":
                with open(GUESS_STATE_PATH,encoding="utf-8") as f:
                    guess_state=json.load(f)
                if guess_state[guess_id]["start"]==False:
                    await mai.finish("没有正在进行的游戏")
                with open(GUESS_DATA_PATH,encoding="utf-8") as f:
                    guess_data=json.load(f)
                for s in guess_state[guess_id]["puzzle"]:
                    if s in guess_state[guess_id]["fail"]:
                        guess_data["total"]["ans"][s]["fail"]+=1
                    elif not s in guess_state[guess_id]["right"]:
                        guess_data["total"]["ans"][s]["false"]+=1
                with open(GUESS_DATA_PATH,"w",encoding="utf-8") as f:
                    json.dump(guess_data,f)
                await mai.send(puzzleGenerate(guess_state[guess_id]["puzzle"],[],guess_state[guess_id]["right"],guess_state[guess_id]["fail"],True))
                guess_state[guess_id]["start"]=False
                guess_state[guess_id]["puzzle"]=[]
                guess_state[guess_id]["open"]=[]
                guess_state[guess_id]["right"]=[]
                guess_state[guess_id]["fail"]=[]
                with open(GUESS_STATE_PATH,"w",encoding="utf-8") as f:
                    json.dump(guess_state,f)
                return
            elif arg[1]=="开" or (len(arg)==2 and len(arg[1])==1):#开或者直接提供字符可以开字符
                with open(GUESS_STATE_PATH,encoding="utf-8") as f:
                    guess_state=json.load(f)
                if len(arg)>2:
                    ch=arg[2][0]#只取第一个字符
                else:
                    ch=arg[1]
                if ch in guess_state[guess_id]["open"]:
                    await mai.finish("这个字符已经被开过了哦")
                with open(GUESS_DATA_PATH,encoding="utf-8") as f:
                    guess_data=json.load(f)
                if "a"<=ch<="z":#大小写同开
                    guess_state[guess_id]["open"]+=[ch.upper(),ch]
                    chs=[ch.upper(),ch]
                elif "A"<=ch<="Z":
                    guess_state[guess_id]["open"]+=[ch,ch.lower()]
                    chs=[ch,ch.lower()]
                elif ch in HIRAGANA:#平片假名同开
                    guess_state[guess_id]["open"]+=[ch,HIRAGANA[ch]]
                    chs=[ch,HIRAGANA[ch]]
                elif ch in KATAKANA:
                    guess_state[guess_id]["open"]+=[KATAKANA[ch],ch]
                    chs=[KATAKANA[ch],ch]
                else:
                    guess_state[guess_id]["open"].append(ch)
                    chs=[ch]
                for c in chs:
                    guess_data["total"]["ch"][c] = guess_data["total"]["ch"].get(c, 0) + 1
                    guess_data["player"][user_id]["ch"][c] = guess_data["player"][user_id]["ch"].get(c, 0) + 1
                with open(GUESS_DATA_PATH,"w",encoding="utf-8") as f:
                    json.dump(guess_data,f)
                for s in guess_state[guess_id]["puzzle"]:
                    if match(s,guess_state[guess_id]["open"]) and not s in guess_state[guess_id]["right"]:
                        guess_state[guess_id]["right"].append(s)
                        guess_state[guess_id]["fail"].append(s)
                        await mai.send(f"{id2songName(s)} 的字母都被开出来了，自动结束该题")
                if len(guess_state[guess_id]["right"])==len(guess_state[guess_id]["puzzle"]):
                    await mai.send("所有题目都被答出，游戏结束")
                    guess_state[guess_id]["start"]=False
                    guess_state[guess_id]["puzzle"]=[]
                    guess_state[guess_id]["open"]=[]
                    guess_state[guess_id]["right"]=[]
                    guess_state[guess_id]["fail"]=[]
                with open(GUESS_STATE_PATH,"w",encoding="utf-8") as f:
                    json.dump(guess_state,f)
                await mai.finish(puzzleGenerate(guess_state[guess_id]["puzzle"],guess_state[guess_id]["open"],guess_state[guess_id]["right"],guess_state[guess_id]["fail"]))
            elif arg[1]=="答":
                if len(arg)>2:#缺参数不予反馈
                    id=alias2id(" ".join(arg[2:]))
                    if id is None:
                        if guess_need_reply:
                            await mai.finish("没有查找到对应的歌，尝试添加一下别名吧")
                        else:
                            return
                    with open(GUESS_STATE_PATH,encoding="utf-8") as f:
                        guess_state=json.load(f)
                    if any(i in guess_state[guess_id]["right"] for i in id):
                        await mai.finish("这首歌已经被答对了哦")
                    guess_right=False
                    for i in id:
                        if i in guess_state[guess_id]["puzzle"]:
                            guess_right=True
                            id=i
                            break
                    if guess_right:
                        guess_state[guess_id]["right"].append(id)
                        with open(GUESS_DATA_PATH,encoding="utf-8") as f:
                            guess_data=json.load(f)
                        guess_data["total"]["ans"][id]["right"]+=1
                        guess_data["player"][user_id]["right"][id]=guess_data["player"][user_id]["right"].get(id,0)+1
                        with open(GUESS_DATA_PATH,"w",encoding="utf-8") as f:
                            json.dump(guess_data,f)
                        await mai.send("回答正确")
                        ggs=guess_state[guess_id].copy()
                        if len(guess_state[guess_id]["right"])==len(guess_state[guess_id]["puzzle"]):
                            await mai.send("所有题目都被答出，游戏结束")
                            guess_state[guess_id]["start"]=False
                            guess_state[guess_id]["puzzle"]=[]
                            guess_state[guess_id]["open"]=[]
                            guess_state[guess_id]["right"]=[]
                            guess_state[guess_id]["fail"]=[]
                        with open(GUESS_STATE_PATH,"w",encoding="utf-8") as f:
                            json.dump(guess_state,f)
                        await mai.finish(puzzleGenerate(ggs["puzzle"],ggs["open"],ggs["right"],ggs["fail"]))
                    else:
                        await mai.finish("回答错误")
            elif arg[1]=="设置":
                if len(arg)==2:
                    await mai.finish("/mai guess 设置 n <数量>    设置题目数量\n/mai guess 设置 jp <on/off>")
                elif arg[2]=="n":
                    if len(arg)<4:
                        await mai.finish("请提供数量")
                    else:
                        try:
                            n=int(arg[3])
                        except:
                            await mai.finish("请提供1-50的正整数")
                        if n<1 or n>50:
                            await mai.finish("请提供1-50的正整数")
                        else:
                            with open(GUESS_CONFIG_PATH,encoding="utf-8") as f:
                                guess_config=json.load(f)
                            guess_config[guess_id]["n"]=n
                            with open(GUESS_CONFIG_PATH,"w",encoding="utf-8") as f:
                                json.dump(guess_config,f)
                            await mai.finish("设置完成！")
                elif arg[2]=="jp":
                    if len(arg)<4:
                        await mai.finish("请输入on/off以开关")
                    if not arg[3] in ["on","off"]:
                        await mai.finish("请输入on/off以开关")
                    with open(GUESS_CONFIG_PATH,encoding="utf-8") as f:
                        guess_config=json.load(f)
                    if arg[3]=="on":
                        guess_config[guess_id]["jp"]=True
                    elif arg[3]=="off":
                        guess_config[guess_id]["jp"]=False
                    with open(GUESS_CONFIG_PATH,"w",encoding="utf-8") as f:
                        json.dump(guess_config,f)
                    await mai.finish("设置完成！")
                else:
                    await mai.finish("/mai guess 设置 n <数量>    设置题目数量")
            elif arg[1]=="排行榜":
                with open(GUESS_DATA_PATH,encoding="utf-8") as f:
                    guess_data=json.load(f)
                with open(GUESS_ACCOUNT_PATH,encoding="utf-8") as f:
                    guess_account=json.load(f)
                guess_score=[]
                for p in guess_data["player"]:
                    tmp=0
                    for s in guess_data["player"][p]["right"]:
                        tmp+=guess_data["player"][p]["right"][s]
                    if tmp:
                        guess_score.append([guess_account[p],tmp,p])
                guess_score=sorted(guess_score,key=lambda x:x[1],reverse=True)
                res="答对题数排行榜：\n"
                n=0
                for p in guess_score:
                    if p[2]==event.get_user_id():
                        res+=f"{p[0]} :  {p[1]}    <--你在这里\n"
                    else:
                        res+=f"{p[0]} :  {p[1]}\n"
                    n+=1
                await mai.finish(res[:-1])
            else:#剩余都默认开歌
                id=alias2id(" ".join(arg[1:]))
                if id is None:
                    if guess_need_reply:
                        await mai.finish("没有查找到对应的歌")
                    else:
                        return
                with open(GUESS_STATE_PATH,encoding="utf-8") as f:
                    guess_state=json.load(f)
                if any(i in guess_state[guess_id]["right"] for i in id):
                    await mai.finish("这首歌已经被答对了哦")
                guess_right=False
                for i in id:
                    if i in guess_state[guess_id]["puzzle"]:
                        guess_right=True
                        id=i
                        break
                if guess_right:
                    guess_state[guess_id]["right"].append(id)
                    with open(GUESS_DATA_PATH,encoding="utf-8") as f:
                        guess_data=json.load(f)
                    guess_data["total"]["ans"][id]+=1
                    guess_data["player"]["right"][id]=guess_data["player"]["right"].get(id,0)+1
                    with open(GUESS_DATA_PATH,"w",encoding="utf-8") as f:
                        json.dump(guess_data,f)
                    await mai.send("回答正确")
                    ggs=guess_state[guess_id].copy()
                    if len(guess_state[guess_id]["right"])==len(guess_state[guess_id]["puzzle"]):
                        await mai.send("所有题目都被答出，游戏结束")
                        guess_state[guess_id]["start"]=False
                        guess_state[guess_id]["puzzle"]=[]
                        guess_state[guess_id]["open"]=[]
                        guess_state[guess_id]["right"]=[]
                        guess_state[guess_id]["fail"]=[]
                    with open(GUESS_STATE_PATH,"w",encoding="utf-8") as f:
                        json.dump(guess_state,f)
                    await mai.finish(puzzleGenerate(ggs["puzzle"],ggs["open"],ggs["right"],ggs["fail"]))
                else:
                    await mai.finish("回答错误")
    elif arg[0]=="霸者进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.A,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}a.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="舞极进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.FC,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}fc.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="舞将进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.SSS,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}sss.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="舞神进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.AP,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}ap.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="舞舞舞进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.FDX,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}fdx.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="舞系列进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.A,user_id)
        path1=PROGRESS_PIC_PATH/f"{user_id}a.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path1)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.FC,user_id)
        path2=PROGRESS_PIC_PATH/f"{user_id}fc.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path2)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.SSS,user_id)
        path3=PROGRESS_PIC_PATH/f"{user_id}sss.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path3)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.AP,user_id)
        path4=PROGRESS_PIC_PATH/f"{user_id}ap.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path4)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.FDX,user_id)
        path5=PROGRESS_PIC_PATH/f"{user_id}fdx.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path5)
        msgs=[]
        for p in [path1,path2,path3,path4,path5]:
            msgs.append(
                    {
                    "type": "node",
                    "data": {
                        "name": "プラナ",
                        "uin": str(event.self_id),
                        "content": MessageSegment.image(p)
                    }
                }
            )
        if "message.group" in event.get_event_name():
            await bot.call_api("send_group_forward_msg",group_id=event.group_id,messages=msgs)
        elif "message.private" in event.get_event_name():
            await bot.call_api("send_private_forward_msg",user_id=event.user_id,messages=msgs)
    elif arg[0]=="DX霸者进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.A,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}dxa.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="DX舞极进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.FC,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}dxfc.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="DX舞将进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.SSS,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}dxsss.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="DX舞神进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.AP,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}dxap.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="DX舞舞舞进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.FDX,user_id)
        path=PROGRESS_PIC_PATH/f"{user_id}dxfdx.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path)
        await mai.finish(MessageSegment.image(path))
    elif arg[0]=="DX舞系列进度":
        if len(arg)>1:
            user_id=arg[1]
        else:
            user_id=event.get_user_id()
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        if (not user_id in query_info) or time.time()-query_info[user_id]>QUERY_COOLDOWN:
            query_info[user_id]=time.time()
            update_state=update(user_id)
            if not update_state:
                await mai.finish("获取数据失败，请查看水鱼绑定的QQ号是否和当前使用的相同")
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.A,user_id)
        path1=PROGRESS_PIC_PATH/f"{user_id}dxa.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path1)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.FC,user_id)
        path2=PROGRESS_PIC_PATH/f"{user_id}dxfc.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path2)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.SSS,user_id)
        path3=PROGRESS_PIC_PATH/f"{user_id}dxsss.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path3)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.AP,user_id)
        path4=PROGRESS_PIC_PATH/f"{user_id}dxap.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path4)
        sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.FDX,user_id)
        path5=PROGRESS_PIC_PATH/f"{user_id}dxfdx.png"
        paint(sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers,path5)
        msgs=[]
        for p in [path1,path2,path3,path4,path5]:
            msgs.append(
                    {
                    "type": "node",
                    "data": {
                        "name": "プラナ",
                        "uin": str(event.self_id),
                        "content": MessageSegment.image(p)
                    }
                }
            )
        if "message.group" in event.get_event_name():
            await bot.call_api("send_group_forward_msg",group_id=event.group_id,messages=msgs)
        elif "message.private" in event.get_event_name():
            await bot.call_api("send_private_forward_msg",user_id=event.user_id,messages=msgs)
    elif arg[0]=="rt排行":
        members=await bot.get_group_member_list(group_id=event.group_id)
        rts={}
        for member in members:
            user_id=str(member["user_id"])
            try:
                with open(r"D:\Nonebot\local\local\plugins\mai\record"+"\\"+f"{user_id}record.json",encoding="utf-8") as f:
                    record=json.load(f)
                    rts[member["user_id"]]=record["rating"]
            except:
                continue
                print(f"正在查询{member['nickname']}的rating")
                rt=get_rating(member["user_id"])
                if rt is not None:
                    rts[member["user_id"]]=rt
        print(rts)
        rts=sorted(rts.items(),key=lambda x:x[1],reverse=True)
        res="群rating排行：（数据源：水鱼）\n"
        n=1
        for p in rts[:RANKLENGTH]:
            name=""
            for member in members:
                if member["user_id"]==p[0]:
                    name=member["nickname"]
                    break
            res+=f"{n}. {name} :  {p[1]}\n"
            n+=1
        msgs=[]
        msgs.append(
                    {
                    "type": "node",
                    "data": {
                        "name": "プラナ",
                        "uin": str(event.self_id),
                        "content": res
                    }
                }
            )
        await bot.call_api("send_group_forward_msg",group_id=event.group_id,messages=msgs)
    elif arg[0]=="霸者排行":
        members=await bot.get_group_member_list(group_id=event.group_id)
        await mai.send(f"查询人数较多，请等待 {round(len(members)*0.2)} 秒喵")
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        querystate=[0,0,0]#未更新人数，更新成功人数，尝试更新人数
        for member in members:
            print(f"正在查询{member['nickname']}的进度")
            user_id=str(member["user_id"])
            if (not user_id in query_info) or time.time()-query_info[user_id]>RANK_QUERY_COOLDOWN:
                query_info[user_id]=time.time()
                update_state=update(user_id)
                time.sleep(0.1)
                if update_state:
                    querystate[1]+=1
                querystate[2]+=1
            else:
                querystate[0]+=1
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        recsid=[]
        for p in os.listdir(r"D:\Nonebot\local\local\plugins\mai\record"):
            if p.endswith("record.json") and len(p)>11 and p[:-11] in [str(member["user_id"]) for member in members]:
                recsid.append(p[:-11])
        progress_all={}
        for user_id in recsid:
            sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(FiNALEType.A,user_id)
            prog=[0,0]#完成，总数
            for p in range(len(sorted_difs_keys)):
                prog[0]+=sorted_difs[p][0]
                prog[1]+=sum(sorted_difs[p])
            progress_all[user_id]=prog
        print(progress_all)
        progress_all=sorted(progress_all.items(),key=lambda x:x[1][0]/x[1][1] if x[1][1] else 0,reverse=True)
        res="群霸者进度排行：（数据源：水鱼）\n"
        n=1
        for p in progress_all[:RANKLENGTH]:
            name=""
            for member in members:
                if str(member["user_id"])==p[0]:
                    name=member["nickname"]
                    break
            res+=f"{n}. {name} :  {p[1][0]}/{p[1][1]} ({p[1][0]/p[1][1]*100:.2f}%)\n"
            n+=1
        res+=f"\n本次未更新人数：{querystate[0]}，更新成功人数：{querystate[1]}，尝试更新人数：{querystate[2]}"
        await mai.finish(res)
    elif arg[0]=="DX霸者排行":
        members=await bot.get_group_member_list(group_id=event.group_id)
        await mai.send(f"查询人数较多，请等待 {round(len(members)*0.2)} 秒喵")
        with open(QUERY_STATE,encoding="utf-8") as f:
            query_info=json.load(f)
        querystate=[0,0,0]#未更新人数，更新成功人数，尝试更新人数
        for member in members:
            print(f"正在查询{member['nickname']}的进度")
            user_id=str(member["user_id"])
            if (not user_id in query_info) or time.time()-query_info[user_id]>RANK_QUERY_COOLDOWN:
                query_info[user_id]=time.time()
                update_state=update(user_id)
                time.sleep(0.1)
                if update_state:
                    querystate[1]+=1
                querystate[2]+=1
            else:
                querystate[0]+=1
        with open(QUERY_STATE,"w",encoding="utf-8") as f:
            json.dump(query_info,f)
        recsid=[]
        for p in os.listdir(r"D:\Nonebot\local\local\plugins\mai\record"):
            if p.endswith("record.json") and len(p)>11 and p[:-11] in [str(member["user_id"]) for member in members]:
                recsid.append(p[:-11])
        progress_all={}
        for user_id in recsid:
            sorted_difs,sorted_cleared_difs,sorted_difs_keys,sorted_vers,sorted_cleared_vers=get_records(ALLPERFECTType.A,user_id)
            prog=[0,0]#完成，总数
            for p in range(len(sorted_difs_keys)):
                prog[0]+=sorted_difs[p][0]
                prog[1]+=sum(sorted_difs[p])
            progress_all[user_id]=prog
        print(progress_all)
        progress_all=sorted(progress_all.items(),key=lambda x:x[1][0]/x[1][1] if x[1][1] else 0,reverse=True)
        res="群DX霸者进度排行：（数据源：水鱼）\n"
        n=1
        for p in progress_all[:RANKLENGTH]:
            name=""
            for member in members:
                if str(member["user_id"])==p[0]:
                    name=member["nickname"]
                    break
            res+=f"{n}. {name} :  {p[1][0]}/{p[1][1]} ({p[1][0]/p[1][1]*100:.2f}%)\n"
            n+=1
        res+=f"\n本次未更新人数：{querystate[0]}，更新成功人数：{querystate[1]}，尝试更新人数：{querystate[2]}"
        await mai.finish(res)

