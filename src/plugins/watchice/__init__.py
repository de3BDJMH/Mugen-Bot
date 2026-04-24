from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg,Arg
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot import get_bot
from nonebot.typing import T_State


import os
import random
import shutil
import json
import datetime
import pathlib

from ...libraries.tools import *
from ...libraries.watchice.paint import distibution as paintdis

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="watchice",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

watch=on_command("看",block=True)
upload=on_command("上传",block=True)
addalias=on_command("添加群友别名",block=True)
delalias=on_command("删除群友别名",block=True)
checkalias=on_command("查看群友别名",block=True)
addmember=on_command("添加群友",block=True)
delmember=on_command("删除群友",block=True)
delimg=on_command("删除",block=True)
watchhelp=on_command("看群友帮助",block=True)
memberlist=on_command("群友列表",block=True)

updatealias=on_command("更新群友别名",block=True)
checkque=on_command("查看队列",block=True)

checkdistribution=on_command("群友图片分布",block=True)

TAG="watchice"

#路径设置
ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent #/server
DATA_PATH=ROOT_PATH/"data"/"watchice"

MEMBER_ALIAS_PATH=DATA_PATH/"member_alias.json"

MEMBER_ALIAS={}
IMG_PATH={}

IMG_ID=DATA_PATH/"img"/"id.json"

def get_member(name):
    for m in MEMBER_ALIAS:
        for a in MEMBER_ALIAS[m]:
            if a.lower()==name.lower():
                return m
    else:
        return ""

def reload_alias():
    global MEMBER_ALIAS
    global IMG_PATH
    with open(MEMBER_ALIAS_PATH,encoding="utf-8") as f:
        MEMBER_ALIAS=json.load(f)

    IMG_PATH={}
    _ORIGIN_PATH=DATA_PATH/"img"
    for m in MEMBER_ALIAS:
        IMG_PATH[m]=_ORIGIN_PATH/m
        try:
            os.mkdir(IMG_PATH[m])
        except:
            continue
reload_alias()

WHITELIST=[558248216,727967933,837222085,791163286,1033530604,640447991,640447991,1021122156]
OPS=[2404164262,2421372100]


@watch.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return

    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().strip()
    img_id=-1
    if " " in arg:
        try:
            target=get_member(arg.split(" ")[0])
            img_id=int(arg.split(" ")[1].strip())
        except:
            target=get_member(arg)
    else:
        target=get_member(arg)
    if target:
        path=IMG_PATH[target]
    else:
        return
    if target=="icy" and not event.group_id in [558248216,837222085,791163286,640447991]:
        return
    imgs=[os.path.join(path,file) for file in os.listdir(path)]
    if imgs:
        #await watch.finish(MessageSegment.image(random.choice(imgs)))#想要关闭全随机就把这行注释掉
        img_ids=os.listdir(path)
        if img_id<=0:
            img_path=random.choice(imgs)
            ctime=os.path.getmtime(img_path)
            ctime=datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
            await watch.finish(MessageSegment.image(img_path)+f"\n图片ID: {img_path.split(os.sep)[-1].split('.')[0]}\n上传时间: {ctime}")
        elif max([int(img_ids[n].split(".")[0]) for n in range(len(img_ids))])<img_id:
            await watch.finish("还没有这么多图片哦")
        elif not str(img_id) in [file.split(".")[0] for file in img_ids]:
            await watch.finish("该编号的图片已被删除")
        else:
            for i in img_ids:
                if i.split(".")[0]==str(img_id):
                    ctime=os.path.getmtime(os.path.join(path,i))
                    ctime=datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
                    await watch.finish(MessageSegment.image(os.path.join(path,i))+f"\n图片ID: {img_id}\n上传时间: {ctime}")
    else:
        await watch.finish("Ta还没有图片哦，试试上传一张吧~")

@upload.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text()
    target=get_member(arg)
    if target:
        que=list(config.state.keys())
        if que:
            que_id=que[-1]+1
            config.state[que_id]=[True,IMG_PATH[target],event.get_user_id()]
        else:
            config.state[0]=[True,IMG_PATH[target],event.get_user_id()]
    else:
        await upload.finish("还没有这个群友哦")

@upload.got("img",prompt="请发送图片")
async def get_img(event:GroupMessageEvent,img:Message=Arg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    bot=get_bot()
    new=img.get("image")
    #que_id=list(config.state.keys())[-1]#备用方案
    for id in config.state:
        if config.state[id][2]==event.get_user_id() and config.state[id][0]:
            que_id=id
            config.state[id][0]=False
            break
    else:
        await upload.finish("上传失败，请重新尝试")
    if new:
        imgfile=new[0].data["file"]
        imgdld=await bot.call_api("get_image",file=imgfile)
        imgdld=imgdld["file"]
        if not IMG_ID.exists():
            with open(IMG_ID,"w",encoding="utf-8") as f:
                json.dump({},f)
        with open(IMG_ID,encoding="utf-8") as f:
            img_ids=json.load(f)
        target=config.state[que_id][1].name
        if target in img_ids:
            img_ids[target]+=1
        else:
            img_ids[target]=1
        with open(IMG_ID,"w",encoding="utf-8") as f:
            json.dump(img_ids,f)
        img_id=img_ids[target]
        shutil.move(imgdld,os.path.join(config.state[que_id][1],f"{img_id}{imgdld[-4:]}"))
        #del config.state[que_id]
        await upload.finish(f"({target}:{img_id})上传成功~")
    else:
        await upload.finish("目前只支持上传图片哦")

@addalias.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().split(" ")
    if len(arg)<2:
        await addalias.finish("请提供原有别名和新增别名")
    target=get_member(arg[0])
    if target:
        for new_alias in arg[1:]:
            new_alias=new_alias.strip()
            for m in MEMBER_ALIAS:
                if new_alias in MEMBER_ALIAS[m]:
                    await addalias.finish("新别名和其他群友已有别名重复了哦，请换一个")
        with open(MEMBER_ALIAS_PATH,encoding="utf-8") as f:
            member_alias=json.load(f)
        member_alias[target]+=arg[1:]
        with open(MEMBER_ALIAS_PATH,"w",encoding="utf-8") as f:
            json.dump(member_alias,f)
        reload_alias()
        await addalias.finish("添加成功")
    else:
        await addalias.finish("这个别名不存在")

@delalias.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().split(" ")
    if len(arg)<2:
        await delalias.finish("请提供原有别名和需要删的别名")
    target=get_member(arg[0])
    if target:
        for new_alias in arg[1:]:
            new_alias=new_alias.strip()
            if not new_alias in MEMBER_ALIAS[target]:
                await addalias.finish("不存在需要删除的别名")
        with open(MEMBER_ALIAS_PATH,encoding="utf-8") as f:
            member_alias=json.load(f)
        for a in member_alias[target].copy():
            if a in arg[1:]:
                member_alias[target].remove(a)
        with open(MEMBER_ALIAS_PATH,"w",encoding="utf-8") as f:
            json.dump(member_alias,f)
        reload_alias()
        await addalias.finish("删除成功")
    else:
        await addalias.finish("不存在这个群友")

@checkalias.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().strip()
    target=get_member(arg)
    if target:
        await checkalias.finish(f"{"，".join(MEMBER_ALIAS[target])}")
    else:
        await checkalias.finish("还没有这个群友哦")

@addmember.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().split(" ")
    if len(arg)<1 or not arg[0]:
        await addmember.finish("需要提供群友名称，可在后面用空格分隔多个别名")
    target=arg[0]
    for c in arg[0]:
        if (not "a"<=c<="z") and (not "0"<=c<="9"):
            await addmember.finish("需要全为小写字母或数字（尽可能有辨识性），可在别名内添加中文别名")
    for m in MEMBER_ALIAS:
        if target in MEMBER_ALIAS[m]:
            await addalias.finish("这个名字和其他群友已有别名重复了哦，请换一个")
    with open(MEMBER_ALIAS_PATH,encoding="utf-8") as f:
        member_alias=json.load(f)
    member_alias[target]=[target]
    if len(arg)>1:
        member_alias[target]+=arg[1:]
    with open(MEMBER_ALIAS_PATH,"w",encoding="utf-8") as f:
        json.dump(member_alias,f)
    reload_alias()
    await addalias.finish("旅行伙伴加入~")

@delmember.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    if not int(event.get_user_id()) in OPS:
        await delmember.finish("无权限")    
    arg=args.extract_plain_text().split(" ")
    if len(arg)<1 or not arg[0]:
        await addmember.finish("需要提供群友别名")
    target=get_member(arg[0])
    if target:
        if not target in MEMBER_ALIAS:
            await delmember.finish("不存在该群友")
        with open(MEMBER_ALIAS_PATH,encoding="utf-8") as f:
            member_alias=json.load(f)
        del member_alias[target]
        with open(MEMBER_ALIAS_PATH,"w",encoding="utf-8") as f:
            json.dump(member_alias,f)
        reload_alias()
        await delmember.finish("删除成功")
    else:
        await delmember.finish("不存在这个群友")

@delimg.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    arg=args.extract_plain_text().split(" ")
    if len(arg)<2:
        await delimg.finish("需要提供别名和图片id")
    try:
        target=get_member(arg[0])
        img_id=int(arg[1].strip())
    except:
        await delimg.finish("需要提供别名和图片id")
    if target:
        path=IMG_PATH[target]
        img_ids=os.listdir(path)
        if not IMG_ID.exists():
            with open(IMG_ID,"w",encoding="utf-8") as f:
                json.dump({},f)
        with open(IMG_ID,encoding="utf-8") as f:
            ids=json.load(f)
        if not str(img_id) in [file.split(".")[0] for file in img_ids]:
            await delimg.finish("该编号图片不存在或已被删除")
        # if not int(event.get_user_id()) in OPS and img_id!=max([int(img_ids[n].split(".")[0]) for n in range(len(img_ids))]):
        #     await delimg.finish(f"仅支持删除最新上传的图（当前：{max([int(img_ids[n].split(".")[0]) for n in range(len(img_ids))])}）")
        if not int(event.get_user_id()) in OPS and img_id!=ids[target]:
            await delimg.finish(f"仅支持删除最新上传的图（当前：{ids[target]}）")
        for i in img_ids:
            if i.split(".")[0]==str(img_id):
                os.remove(os.path.join(path,i))
                await delimg.finish("删除成功")
    else:
        await delimg.finish("需要提供别名和图片id")

@watchhelp.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    if not event.group_id in WHITELIST:
        return
    await addalias.finish("所有人可用：\n"
                          +"    看图片      “看<群友别名> [id]”\n"
                          +"    添加群友      “添加群友 <群友ID> [别名1] [别名2]...”\n"
                          +"    添加别名      “添加群友别名 <已有别名> <新别名1> [新别名2]...”\n"
                          +"    删除别名      “删除群友别名 <已有别名> <需要删除的别名1> [需要删除的别名2]...”\n"
                          +"    查看别名      “查看群友别名 <已有别名>”\n"
                          +"    上传图片      “上传<群友别名>”\n"
                          +"    删除图片      “删除<群友别名> <图片ID>”\n"
                          +"    群友图片分布      “群友图片分布”\n"
                          +"管理可用：\n"
                          +"    删除图片      “删除<群友别名> <图片ID>”\n"
                          +"    删除群友      “删除群友 <群友别名>”\n"
                          +"\n"
                          +"注：\n"
                          +"    非管理只能删除最后一张上传的图片\n"
                          +"    上传时请注意隐私，所有人可见")

@memberlist.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    # if not event.group_id in WHITELIST:
    #     return
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    if not IMG_ID.exists():
        with open(IMG_ID,"w",encoding="utf-8") as f:
            json.dump({},f)
    with open(IMG_ID,encoding="utf-8") as f:
        img_ids=json.load(f)
    msgs=[]
    for m in MEMBER_ALIAS:
        if m=="icy" and not event.group_id in [558248216,837222085,791163286,640447991,640447991]:
            continue
        msgs.append({
                        "type": "node",
                        "data": {
                            "name": "プラナ",
                            "uin": str(event.self_id),
                            "content": f"ID: {m}\n别名: {"，".join(MEMBER_ALIAS[m])}\n当前图片数量: {img_ids[m] if m in img_ids else 0}"
                        }
                    }
                )
    await bot.call_api("send_group_forward_msg",group_id=event.group_id,messages=msgs)

@updatealias.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    if not event.group_id in WHITELIST:
        return
    if event.get_user_id()!="2404164262":
        await updatealias.finish("无权限")
    else:
        reload_alias()
        await updatealias.finish("更新完毕")

@checkque.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    if not event.group_id in WHITELIST:
        return
    if event.get_user_id()!="2404164262":
        await updatealias.finish("无权限")
    msgs=[]
    for id in config.state:
        msgs.append(
            ({
                    "type": "node",
                    "data": {
                        "name": "プラナ",
                        "uin": str(event.self_id),
                        "content": f"ID: {id}\n    上传对象: {config.state[id][1].split('\\')[-1]}\n    上传者: {config.state[id][2]}\n    当前状态: {config.state[id][0]}\n"
                    }
                }
            )
        )
    if msgs:
        await bot.call_api("send_group_forward_msg",group_id=event.group_id,messages=msgs)
    else:
        await checkque.finish("当前没有人上传图片")

@checkdistribution.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:GroupMessageEvent,args: Message = CommandArg()):
    
    plugin=MGPlugin(TAG)
    if not plugin.getPluginState():
        return
    if not plugin.getGroupPluginState(event):
        return
    
    if not IMG_ID.exists():
        with open(IMG_ID,"w",encoding="utf-8") as f:
            json.dump({},f)
    with open(IMG_ID,encoding="utf-8") as f:
        dc=json.load(f)
    path=DATA_PATH/"out"/"out.png"
    if not event.group_id in [558248216,837222085,791163286,640447991,640447991]:
        del dc["icy"]
    paintdis(dc,MEMBER_ALIAS,path)
    await checkdistribution.finish(MessageSegment.image(path))
    
