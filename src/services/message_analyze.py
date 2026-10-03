from pydantic import BaseModel
from collections import Counter
import datetime
import json

from ..storage import message_analyze as message_analyze_storage
from ..storage.log import message as message_storage
from ..storage.log.database import transaction

def get_group_config(group_id:int)->message_analyze_storage.GroupConfig|None:
    """读取群聊配置"""
    return message_analyze_storage.get_group_config(group_id)

def get_group_message_by_time(conn,group_id:int,start_time:int,end_time:int)->list:
    """根据指定时间获取指定群聊的消息"""
    return message_storage.get_group_message_by_time(conn,group_id,start_time,end_time)

class MessageAnalyzeResult(BaseModel):
    """消息分析结果"""
    message_count:int#消息总数
    character_total:int#总字数
    #character_count:dict[str,int]#字：数量
    sender:dict[int,int]#发送者：消息数
    sender_count:int#参与人数
    send_time_distribution:dict[int,int]#发送时间：消息数（按小时统计）
    image_count:int#图片数量
    reply_count:dict[int,int]#被回复次数

def analyze_messages(messages:list)->MessageAnalyzeResult:
    """分析给定消息列表"""
    #要求：
    #1.所属群聊
    #2.统计时间范围
    #3.基础数据：
    #  - 消息数量
    #  - 参与人数
    #  - 字数
    #  - 图片数
    #  - ...
    #4.消息发送时间分布
    #5.发言数排行
    #6.被at/回复最多次的
    #7....
    character_count=Counter()#字：数量
    sender=Counter()#发送者：消息数
    send_time_distribution=Counter()#发送时间：消息数（按小时统计）
    image_count=0#图片数量
    reply_count=Counter()#被回复次数
    for message in messages:
        #字符数量
        character_count.update(message["plain_text"])
        #发送者
        sender[message["sender_id"]]+=1
        #发送时间
        send_time_distribution[datetime.datetime.fromtimestamp(message["time"]).hour]+=1
        for msgsegment in json.loads(message["message_json"]):
            #图片数量
            if msgsegment["type"]=="image":
                image_count+=1
            #被at/回复次数
            if msgsegment["type"]=="reply":
                with transaction() as conn:
                    reply_message=message_storage.get_message_by_message_id(conn,msgsegment["data"]["id"],message["self_id"])
                if reply_message is not None:
                    reply_count[reply_message["sender_id"]]+=1
            elif msgsegment["type"]=="at":
                qq=msgsegment["data"]["qq"]
                if qq!="all":
                    reply_count[qq]+=1

    return MessageAnalyzeResult(
        message_count=len(messages),
        character_total=character_count.total(),
        #character_count=dict(character_count),
        sender=dict(sender),
        sender_count=len(sender),
        send_time_distribution=dict(send_time_distribution),
        image_count=image_count,
        reply_count=dict(reply_count)
    )

with transaction() as conn:
    messages=get_group_message_by_time(conn,group_id=558248216,start_time=1788451200,end_time=1791043200)
    result=analyze_messages(messages)
    print(result.model_dump_json(indent=4,ensure_ascii=False))