from nonebot.adapters.onebot.v11 import MessageEvent,GroupMessageEvent,Bot,Message
from nonebot import logger

import json
import time

from ...storage.log.database import transaction
from ...storage.log import message as message_storage

async def fill_forward(bot:Bot,data,seen:set|None=None):
    """处理转发消息（可处理嵌套）"""
    if seen is None:
        seen=set()

    if isinstance(data,list):#列表，逐条处理消息
        for item in data:
            await fill_forward(bot,item,seen)
        return
    if not isinstance(data,dict):#啥也不是
        return

    if data.get("type")=="forward":
        seg_data=data.get("data",{})
        forward_id=seg_data.get("id")
        if forward_id and "content" not in seg_data and forward_id not in seen:#防嵌套循环，有煞笔会构造包含自身的转发消息
            seen.add(forward_id)
            try:
                seg_data["content"]=await bot.get_forward_msg(id=forward_id)
                await fill_forward(bot,seg_data["content"],seen)
            except Exception:#转发消息内容获取过期时候还是需要记录发送过消息，但是内容留空
                pass

    for value in data.values():
        await fill_forward(bot,value,seen)

async def add(bot:Bot,event:MessageEvent):
    """将MessageEvent对象解析为sql可存储对象并存储"""
    message_id=event.message_id
    self_id=event.self_id
    message_type=event.message_type
    group_id=event.group_id if isinstance(event,GroupMessageEvent) else None
    sender_id=event.user_id
    send_time=event.time
    message=event.get_message()
    message_data=[{"type":seg.type,"data":seg.data.copy()} for seg in message]
    await fill_forward(bot,message_data)
    message_json=json.dumps(message_data,ensure_ascii=False,separators=(",",":"))
    plain_text=message.extract_plain_text()#转发消息的提取是空字符串

    with transaction() as conn:#事务，获取连接
        return message_storage.add(
            conn,
            message_id=message_id,
            self_id=self_id,
            type=message_type,
            group_id=group_id,
            sender_id=sender_id,
            time=send_time,
            message_json=message_json,
            plain_text=plain_text)#执行，出问题了就rollback
    #离开会自己断连

def add_bot_message(bot:Bot,api:str,data:dict,result:dict):
    """解析bot自己发送的信息"""
    message_id=result["message_id"]
    self_id=int(bot.self_id)
    if api=="send_msg":
        message_type=data["message_type"]
    elif api=="send_group_msg":
        message_type="group"
    elif api=="send_private_msg":
        message_type="private"
    else:
        return
    group_id=data.get("group_id") if message_type=="group" else None
    message=Message(data["message"])
    message_json=json.dumps([{"type":seg.type,"data":seg.data} for seg in message],ensure_ascii=False,separators=(",",":"))
    plain_text=message.extract_plain_text()

    with transaction() as conn:
        return message_storage.add(
            conn,
            message_id=message_id,
            self_id=self_id,
            type=message_type,
            group_id=group_id,
            sender_id=self_id,
            time=int(time.time()),
            message_json=message_json,
            plain_text=plain_text
        )

async def add_bot_forward(bot:Bot,api:str,data:dict,result:dict):
    """解析bot发送的转发消息"""
    message_id=result["message_id"]
    self_id=int(bot.self_id)
    if api=="send_group_forward_msg":
        message_type="group"
        group_id=data["group_id"]
    elif api=="send_private_forward_msg":
        message_type="private"
        group_id=None
    else:
        return
    messages=data["messages"]
    await fill_forward(bot,messages)
    message_json=json.dumps(messages,ensure_ascii=False,separators=(",",":"))
    plain_text=""#转发消息无法解析纯文本

    with transaction() as conn:
        return message_storage.add(
            conn,
            message_id=message_id,
            self_id=self_id,
            type=message_type,
            group_id=group_id,
            sender_id=self_id,
            time=int(time.time()),
            message_json=message_json,
            plain_text=plain_text
        )
    