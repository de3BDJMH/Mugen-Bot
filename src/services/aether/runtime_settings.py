from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.storage.aether import AetherConfigError,load_json_object,save_json_atomic


VERSION=1
EDITABLE_FIELDS={
    "camp_stay_time",
    "acceleration_balanced_min_wait_seconds",
    "acceleration_ticket_reserve",
    "acceleration_rush_ignore_reserve",
    "consecutive_failure_limit",
    "ntfy_topic",
    "ntfy_server",
    "account_usernames",
    "command_superuser_only",
}
DOCUMENT_FIELDS=EDITABLE_FIELDS


@dataclass(frozen=True)
class RuntimeSettings:
    camp_stay_time:int
    account_usernames:tuple[str,...]
    command_superuser_only:bool
    acceleration_balanced_min_wait_seconds:int
    acceleration_ticket_reserve:int
    acceleration_rush_ignore_reserve:bool
    consecutive_failure_limit:int
    ntfy_topic:str|None
    ntfy_server:str

    def public_payload(self)->dict[str,Any]:
        return {
            "version":VERSION,
            "camp_stay_time":self.camp_stay_time,
            "acceleration_balanced_min_wait_seconds":self.acceleration_balanced_min_wait_seconds,
            "acceleration_ticket_reserve":self.acceleration_ticket_reserve,
            "acceleration_rush_ignore_reserve":self.acceleration_rush_ignore_reserve,
            "consecutive_failure_limit":self.consecutive_failure_limit,
            "ntfy_topic":self.ntfy_topic,
            "ntfy_server":self.ntfy_server,
            "account_usernames":list(self.account_usernames),
            "command_superuser_only":self.command_superuser_only,
        }


def runtime_settings_path()->Path:
    from . import config as cfg

    return Path(cfg.AETHER_CONFIG_DIR)/"settings.json"


def _integer(value:Any,label:str,minimum:int,maximum:int)->int:
    if (
        isinstance(value,bool)
        or not isinstance(value,int)
        or not minimum<=value<=maximum
    ):
        raise AetherConfigError(f"{label}必须是 {minimum}~{maximum} 的整数")
    return value


def _parse_document(payload:Any)->RuntimeSettings:
    if not isinstance(payload,dict) or payload.get("version")!=VERSION:
        raise AetherConfigError("Aether 运行设置版本无效")
    if set(payload)!={"version",*DOCUMENT_FIELDS}:
        raise AetherConfigError("Aether 运行设置字段无效")
    usernames=payload["account_usernames"]
    if (
        not isinstance(usernames,list)
        or not usernames
        or not all(isinstance(username,str) for username in usernames)
    ):
        raise AetherConfigError("account_usernames 必须是不重复的非空字符串数组")
    usernames=[username.strip() for username in usernames]
    if not all(usernames) or len(set(usernames))!=len(usernames):
        raise AetherConfigError("account_usernames 必须是不重复的非空字符串数组")
    command_superuser_only=payload["command_superuser_only"]
    rush_ignore_reserve=payload["acceleration_rush_ignore_reserve"]
    if not isinstance(command_superuser_only,bool):
        raise AetherConfigError("command_superuser_only 必须是 boolean")
    if not isinstance(rush_ignore_reserve,bool):
        raise AetherConfigError("acceleration_rush_ignore_reserve 必须是 boolean")
    topic=payload["ntfy_topic"]
    if topic is not None:
        if not isinstance(topic,str):
            raise AetherConfigError("ntfy_topic 必须是 string 或 null")
        topic=topic.strip() or None
        if topic is not None and len(topic)>200:
            raise AetherConfigError("ntfy_topic 最长为 200 个字符")
    server=payload["ntfy_server"]
    if not isinstance(server,str):
        raise AetherConfigError("ntfy_server 必须是 string")
    server=server.strip().rstrip("/")
    parsed=urlsplit(server)
    if (
        len(server)>500
        or parsed.scheme not in {"http","https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise AetherConfigError("ntfy_server 必须是有效的 HTTP(S) 地址")
    return RuntimeSettings(
        camp_stay_time=_integer(payload["camp_stay_time"],"camp_stay_time",0,3600),
        account_usernames=tuple(usernames),
        command_superuser_only=command_superuser_only,
        acceleration_balanced_min_wait_seconds=_integer(
            payload["acceleration_balanced_min_wait_seconds"],
            "acceleration_balanced_min_wait_seconds",
            0,
            86400,
        ),
        acceleration_ticket_reserve=_integer(
            payload["acceleration_ticket_reserve"],
            "acceleration_ticket_reserve",
            0,
            1000000,
        ),
        acceleration_rush_ignore_reserve=rush_ignore_reserve,
        consecutive_failure_limit=_integer(
            payload["consecutive_failure_limit"],
            "consecutive_failure_limit",
            1,
            100,
        ),
        ntfy_topic=topic,
        ntfy_server=server,
    )


def load_runtime_settings(path:Path|None=None)->RuntimeSettings:
    target=path or runtime_settings_path()
    return _parse_document(load_json_object(target,label="Aether 运行设置"))


def save_runtime_settings(values:Any,*,path:Path|None=None)->RuntimeSettings:
    if not isinstance(values,dict) or set(values)!=EDITABLE_FIELDS:
        raise AetherConfigError("Aether 可编辑运行设置字段无效")
    target=path or runtime_settings_path()
    payload={"version":VERSION,**values}
    settings=_parse_document(payload)
    save_json_atomic(target,{
        "version":VERSION,
        "camp_stay_time":settings.camp_stay_time,
        "account_usernames":list(settings.account_usernames),
        "command_superuser_only":settings.command_superuser_only,
        "acceleration_balanced_min_wait_seconds":settings.acceleration_balanced_min_wait_seconds,
        "acceleration_ticket_reserve":settings.acceleration_ticket_reserve,
        "acceleration_rush_ignore_reserve":settings.acceleration_rush_ignore_reserve,
        "consecutive_failure_limit":settings.consecutive_failure_limit,
        "ntfy_topic":settings.ntfy_topic,
        "ntfy_server":settings.ntfy_server,
    })
    return settings
