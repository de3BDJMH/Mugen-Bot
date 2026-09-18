from pathlib import Path
import logging

from src.storage.aether import load_json_object,save_json_atomic,AetherConfigError


LEVELS={"silent","errors","summary","detailed"}


def settings_path()->Path:
    from .config import AETHER_CONFIG_DIR
    return Path(AETHER_CONFIG_DIR)/"notifications.json"


def load_settings()->dict:
    path=settings_path()
    if not path.exists():
        return {"level":"summary","qq_recipients":[]}
    return validate_settings(load_json_object(path,label="Aether 通知配置"))


def validate_settings(value:dict)->dict:
    if not isinstance(value,dict) or set(value)!={"level","qq_recipients"}:
        raise AetherConfigError("通知配置字段无效")
    if not isinstance(value["level"],str) or value["level"] not in LEVELS:
        raise AetherConfigError("通知级别无效")
    recipients=value["qq_recipients"]
    if not isinstance(recipients,list) or len(recipients)>20 or any(
        not isinstance(item,str) or not item.isascii() or not item.isdigit() or not 5<=len(item)<=15
        for item in recipients
    ):
        raise AetherConfigError("通知 QQ 必须是有效号码列表")
    return {"level":value["level"],"qq_recipients":list(dict.fromkeys(recipients))}


def save_settings(value:dict)->dict:
    value=validate_settings(value)
    save_json_atomic(settings_path(),value)
    return value


def allows(kind:str)->bool:
    try:
        level=load_settings()["level"]
    except (AetherConfigError,OSError):
        logging.exception("读取 Aether 通知设置失败")
        level="summary"
    return level=="detailed" or kind=="error" and level in {"errors","summary"} or kind=="summary" and level=="summary"


async def notify_web(message:str)->None:
    from nonebot import get_bots,get_driver
    settings=load_settings()
    recipients=settings["qq_recipients"] or sorted(get_driver().config.superusers)
    bots=list(get_bots().values())
    if not bots:
        logging.warning("Aether 通知未发送：QQ Bot 未连接")
        return
    for user_id in recipients:
        if str(user_id).isdigit():
            try:
                await bots[0].call_api("send_private_msg",user_id=int(user_id),message=message)
            except Exception:
                logging.exception("Aether QQ 通知发送失败")
