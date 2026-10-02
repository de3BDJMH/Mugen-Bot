from nonebot.adapters.onebot.v11 import MessageEvent,GroupMessageEvent,Bot,Message
from typing import TYPE_CHECKING#防止循环引用用的

import json

from ...storage.log.database import transaction
from ...storage.log import message as message_storage
from ...storage.log import command as command_storage
if TYPE_CHECKING:
    from ...command.base import Command

def add(cmd:"Command"):
    """解析command并存储"""
    params=cmd.log_params()
    with transaction() as conn:
        message_id=message_storage.get_id_by_message_id(conn,cmd.message_id,cmd.self_id)
        if message_id is None:
            raise ValueError("未找到Command对应的Message记录")
        return command_storage.add(conn,message_id=message_id,command_key=cmd.key,valid=cmd.valid,params_json=json.dumps(params,ensure_ascii=False,separators=(",",":")))