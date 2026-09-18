from nonebot.adapters.onebot.v11 import MessageEvent,GroupMessageEvent

import json

from ...storage.log.database import transaction
from ...storage.log import message as message_storage

def add(event:MessageEvent):
    """将MessageEvent对象解析为sql可存储对象并存储"""
    message_id=event.message_id
    self_id=event.self_id
    message_type=event.message_type
    group_id=event.group_id if isinstance(event,GroupMessageEvent) else None
    sender_id=event.user_id
    time=event.time
    message=event.get_message()
    message_json=json.dumps([{"type":seg.type,"data":seg.data} for seg in message],ensure_ascii=False,separators=(",",":"))
    plain_text=message.extract_plain_text()

    with transaction() as conn:#事务，获取连接
        return message_storage.add(
            conn,
            message_id=message_id,
            self_id=self_id,
            type=message_type,
            group_id=group_id,
            sender_id=sender_id,
            time=time,
            message_json=message_json,
            plain_text=plain_text)#执行，出问题了就rollback
    #离开会自己断连