from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.plugin import on_command
from nonebot.plugin import on_message
from nonebot.params import CommandArg
from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Event,GroupMessageEvent,PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent


import pathlib
import json
import os
import sqlite3 as sql
import datetime

from ...libraries.tools import *

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="CharCounter",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="charcounter"
MGPLUGIN=MGPlugin(TAG)

DATA_PATH=MGPLUGIN.data_path

commands = on_command("character_counter", block=True,aliases={"chc"})
statistics = on_message()

PATH=DATA_PATH/"database"/"data.db"

@statistics.handle()
async def private(bot:Bot,event:MessageEvent):

    if not MGPLUGIN.getPluginState():
        return
    if not MGPLUGIN.getGroupPluginState(event):
        return

    if "message.group" in event.get_event_name():#是群聊
        id=f"group{event.group_id}"
        id_member=event.get_user_id()
    elif "message.private" in event.get_event_name():#是私聊
        id=f"private{event.user_id}"
    else:
        return
    if not os.path.exists(DATA_PATH/"database"/f"{id}.db"):#不存在则创建
        with open(DATA_PATH/"database"/f"{id}.db","w",encoding="utf-8") as f:
            pass
    message_text=event.get_message().extract_plain_text()#获取用户输入内容
    #存储总字符
    table=datetime.date.today().strftime("%Y_%m_%d")#日期做表名，记录变化
    if not PATH.exists():#不存在则创建，data.db很重要
        with open(PATH, "w", encoding="utf-8") as f:
            pass
    conn=sql.connect(PATH)
    cursor=conn.cursor()
    cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table}` (c TEXT PRIMARY KEY, n INT)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS `{id}` (c TEXT PRIMARY KEY, n INT)")
    tmp={}
    for c in message_text:
        if c in tmp:
            tmp[c]+=1
        else:
            tmp[c]=1
    for c in tmp:
        n=tmp[c]
        cursor.execute(f"INSERT INTO `{table}` (c, n) VALUES (?, ?) ON CONFLICT(c) DO UPDATE SET n = n + excluded.n",(c,n))
        cursor.execute(f"INSERT INTO `{id}` (c, n) VALUES (?, ?) ON CONFLICT(c) DO UPDATE SET n = n + excluded.n",(c,n))
    conn.commit()
    conn.close()
    #单独处理群聊
    if "message.group" in event.get_event_name():
        table=id_member#用户id做表名
        conn=sql.connect(DATA_PATH/"database"/f"{id}.db")
        cursor=conn.cursor()
        cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table}` (c TEXT PRIMARY KEY, n INT)")
        for c in tmp:
            n=tmp[c]
            cursor.execute(f"INSERT INTO `{table}` (c, n) VALUES (?, ?) ON CONFLICT(c) DO UPDATE SET n = n + excluded.n",(c,n))
        conn.commit()
        conn.close()

@commands.handle()
async def handle_function(matcher:Matcher,bot:Bot,event:Event,args: Message = CommandArg()):
    arg=args.extract_plain_text().split(" ")
    if "message.group" in event.get_event_name():
        id=f"group{event.group_id}"
    elif "message.private" in event.get_event_name():
        id=f"private{event.user_id}"
    if arg[0]=="字符统计":
        conn=sql.connect(PATH)
        cursor=conn.cursor()
        cursor.execute(f"SELECT * FROM '{id}'")#获取数据
        rows = cursor.fetchall()
        conn.close()
        res={}
        for row in rows:
            res[row[0]]=res.get(row[0],0)+row[1]
        res=[(c,res[c]) for c in res]
        res.sort(key=lambda x: x[1],reverse=True)
        if "group" in id:
            msg="本群聊天中最常用字符统计：\n数据记录起始于2024.10.21 01:00\n"
        else:
            msg="你和普拉娜聊天中最常用字符统计：\n数据记录起始于2024.10.21 01:00\n"
        for n in range(20):
            if n>=len(res):
                break
            cs1=res[n]
            if n+20<len(res):
                cs2=res[n+20]
                msg+=f"  {cs1[0]}:  {cs1[1]:<8}|      {cs2[0]}:  {cs2[1]}\n"
            else:
                msg+=f"  {cs1[0]}:  {cs1[1]}\n"
        msg+="数据来源有限，仅供参考"
        await commands.send(msg)
    elif arg[0]=="总字符统计":
        num=20
        if len(arg)>1:
            try:
                num=int(arg[1])
            except:
                await commands.send("请输入有效的数字")
        conn=sql.connect(PATH)
        cursor=conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        tables=[table[0] for table in tables]#获取所有表名
        res={}
        for table in tables:
            if "group" in table or "private" in table:#只要时间的
                continue
            cursor.execute(f"SELECT * FROM '{table}'")#获取数据
            rows = cursor.fetchall()
            for row in rows:
                res[row[0]]=res.get(row[0],0)+row[1]
        conn.close()
        res=[(c,res[c]) for c in res]
        res.sort(key=lambda x: x[1],reverse=True)
        msg="聊天中最常用字符统计：\n数据记录起始于2024.10.21 01:00\n"
        for n in range(num):
            if n>=len(res):
                break
            cs1=res[n]
            if n+num<len(res):
                cs2=res[n+num]
                msg+=f"  {cs1[0]}:  {cs1[1]:<8}|      {cs2[0]}:  {cs2[1]}\n"
            else:
                msg+=f"  {cs1[0]}:  {cs1[1]}\n"
        msg+="数据来源有限，仅供参考"
        await commands.send(msg)
    elif arg[0]=="查询":
        num=20
        if not "message.group" in event.get_event_name():
            await commands.finish("该指令仅可在群聊中使用")
        if len(arg)==1:
            query_id=event.get_user_id()
        else:
            query_id=arg[1]
        id=f"group{event.group_id}"
        conn=sql.connect(DATA_PATH/"database"/f"{id}.db")
        cursor=conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        tables=[table[0] for table in tables]
        if not query_id in tables:
            await commands.finish("没有查询到该用户的数据")
        user_data=await bot.call_api("get_group_member_info",group_id=event.group_id,user_id=int(query_id),no_cache=True)
        msg="在本群中聊天中最常用字符统计：\n数据记录起始于2024.12.4 23:52（注意：晚于总字符统计的数据起始时间）\n"
        msg+=f"查询用户群昵称：{user_data["card"]}\n"
        cursor.execute(f"SELECT * FROM '{query_id}'")#获取数据
        rows = cursor.fetchall()
        conn.close()
        res={}
        for row in rows:
            res[row[0]]=res.get(row[0],0)+row[1]
        res=[(c,res[c]) for c in res]
        res.sort(key=lambda x: x[1],reverse=True)
        for n in range(num):
            if n>=len(res):
                break
            cs1=res[n]
            if n+num<len(res):
                cs2=res[n+num]
                msg+=f"  {cs1[0]}:  {cs1[1]:<8}|      {cs2[0]}:  {cs2[1]}\n"
            else:
                msg+=f"  {cs1[0]}:  {cs1[1]}\n"
        msg+="注：数据统计起始时间有差距，非统计总字符数量起始时间"
        msgs=[
            {
                "type": "node",
                "data": {
                    "name": "プラナ",
                    "uin": str(event.self_id),
                    "content": msg
                }
            }
        ]
        if "message.group" in event.get_event_name():
            await bot.send_group_forward_msg(group_id=event.group_id, messages=msgs)
        elif "message.private" in event.get_event_name():
            await bot.send_private_forward_msg(user_id=event.user_id, messages=msgs)
        
