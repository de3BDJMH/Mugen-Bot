from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent,GroupMessageEvent

import json

from ...storage.log.database import transaction
from ...storage.log import command as command_storage
from ...storage.log import message as message_storage

COMMAND_REGISTRY:dict[type[Matcher],str]={}#指令注册字典/注册表
def register(matcher:type[Matcher],command_key:str):
    """注册指令"""
    COMMAND_REGISTRY[matcher]=command_key

def add(event:MessageEvent,command_key:str,args:list[str]):
    """转义command并存储"""
    with transaction() as conn:
        message_id=message_storage.get_id_by_message_id(conn=conn,message_id=event.message_id,self_id=event.self_id)#吧onebot的id转译成log中使用的id
        if message_id is None:
            raise LookupError(f"找不到对应的消息日志：self_id={event.self_id},message_id={event.message_id}")
        return command_storage.add(conn=conn,message_id=message_id,command_key=command_key,args_json=json.dumps(args))