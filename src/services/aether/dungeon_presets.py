from pathlib import Path
from typing import Any,Iterable

from . import config as cfg
from src.storage.aether import AetherConfigError,load_json_object,save_json_atomic


VERSION=1
VISIBILITIES={"private","friends","public"}
DIFFICULTIES={"简单","普通","困难","极难"}


def dungeon_presets_path()->Path:
    return Path(cfg.AETHER_CONFIG_DIR)/"dungeon_presets.json"


def load_dungeon_presets_config(path:Path|None=None)->dict[str,Any]:
    payload=load_json_object(path or dungeon_presets_path(),label="Aether 地下城预设")
    if payload.get("version")!=VERSION or set(payload)!={"version","presets"}:
        raise AetherConfigError("Aether 地下城预设文件结构无效")
    presets=payload["presets"]
    if not isinstance(presets,dict) or not presets:
        raise AetherConfigError("Aether 地下城预设必须是非空 object")
    return presets


def _text(value:Any,label:str,max_length:int=100)->str:
    if not isinstance(value,str) or not value.strip() or len(value)>max_length:
        raise AetherConfigError(f"{label}必须是 1~{max_length} 个字符的字符串")
    return value.strip()


def _member(value:Any,label:str)->dict[str,Any]:
    if isinstance(value,(list,tuple)):
        if len(value)!=2:
            raise AetherConfigError(f"{label}格式无效")
        username=_text(value[0],f"{label}.username")
        if isinstance(value[1],str) and value[1].lower() in {
            "friend","offline_friend","offline"
        }:
            return {
                "username":username,"kind":"friend","preset_index":None,
                "leave_after_enter":False,
            }
        value={
            "username":username,"kind":"owned","preset_index":value[1],
            "leave_after_enter":False,
        }
    if (
        not isinstance(value,dict)
        or not {"username","kind","preset_index"}<=set(value)
        or not set(value)<={"username","kind","preset_index","leave_after_enter"}
    ):
        raise AetherConfigError(f"{label}字段无效")
    username=_text(value["username"],f"{label}.username")
    kind=value["kind"]
    if kind not in {"owned","friend"}:
        raise AetherConfigError(f"{label}.kind 必须是 owned 或 friend")
    preset_index=value["preset_index"]
    if kind=="owned":
        if isinstance(preset_index,bool) or not isinstance(preset_index,int) or not 0<=preset_index<=4:
            raise AetherConfigError(f"{label}.preset_index 必须是 0~4")
    elif preset_index is not None:
        raise AetherConfigError(f"{label}是 offline friend，不能配置 preset_index")
    leave_after_enter=value.get("leave_after_enter",False)
    if not isinstance(leave_after_enter,bool):
        raise AetherConfigError(f"{label}.leave_after_enter 必须是 boolean")
    if kind=="friend" and leave_after_enter:
        raise AetherConfigError(f"{label}是 offline friend，不能配置进入后退出")
    return {
        "username":username,"kind":kind,"preset_index":preset_index,
        "leave_after_enter":leave_after_enter,
    }


def validate_dungeon_presets(
    value:Any,
    *,
    owned_characters:Iterable[str],
    layout_rule_keys:Iterable[str],
    dungeon_ids:Iterable[str]|None=None,
    event_ids:Iterable[str]|None=None,
    expected_keys:Iterable[str]|None=None,
)->dict[str,dict[str,Any]]:
    if not isinstance(value,dict) or not 1<=len(value)<=100:
        raise AetherConfigError("地下城预设必须是包含 1~100 项的 object")
    if expected_keys is not None and not set(expected_keys)<=set(value):
        raise AetherConfigError("不能删除已有地下城预设")
    owned=set(owned_characters)
    layouts=set(layout_rule_keys)
    dungeons=set(dungeon_ids) if dungeon_ids is not None else None
    events=set(event_ids) if event_ids is not None else None
    result={}
    for raw_key,raw in value.items():
        key=_text(raw_key,"地下城预设 key")
        if not isinstance(raw,dict):
            raise AetherConfigError(f"地下城预设 {key} 必须是 object")
        current=dict(raw)
        legacy_opener="opener" not in current
        current.setdefault("opener",None)
        current.setdefault("captain",None)
        current.setdefault("event_overrides",{})
        if set(current)!={
            "name","preset_id","difficulty","party","visibility","layout_rule","captain",
            "opener","event_overrides"
        }:
            raise AetherConfigError(f"地下城预设 {key} 字段无效")
        name=_text(current["name"],f"地下城预设 {key}.name",200)
        preset_id=_text(current["preset_id"],f"地下城预设 {key}.preset_id")
        if dungeons is not None and preset_id not in dungeons:
            raise AetherConfigError(f"地下城预设 {key}.preset_id 无效：{preset_id}")
        difficulty=_text(current["difficulty"],f"地下城预设 {key}.difficulty")
        if difficulty not in DIFFICULTIES:
            raise AetherConfigError(f"地下城预设 {key}.difficulty 无效")
        visibility=current["visibility"]
        if visibility not in VISIBILITIES:
            raise AetherConfigError(f"地下城预设 {key}.visibility 无效")
        layout_rule=_text(current["layout_rule"],f"地下城预设 {key}.layout_rule")
        if layout_rule not in layouts:
            raise AetherConfigError(f"地下城预设 {key} 引用了不存在的布局规则：{layout_rule}")
        raw_party=current["party"]
        if not isinstance(raw_party,(list,tuple)) or not 1<=len(raw_party)<=3:
            raise AetherConfigError(f"地下城预设 {key}.party 必须包含 1~3 名成员")
        party=[
            _member(member,f"地下城预设 {key}.party[{index}]")
            for index,member in enumerate(raw_party)
        ]
        usernames=[member["username"] for member in party]
        if len(set(usernames))!=len(usernames):
            raise AetherConfigError(f"地下城预设 {key}.party 不能包含重复角色")
        owned_members=[]
        for member in party:
            if member["kind"]!="owned":
                continue
            if member["username"] not in owned:
                raise AetherConfigError(
                    f"地下城预设 {key} 包含不存在的 owned 角色：{member['username']}"
                )
            owned_members.append(member["username"])
        if not owned_members:
            raise AetherConfigError(f"地下城预设 {key} 至少需要一名 owned 角色")
        opener=current["opener"]
        captain=current["captain"]
        if legacy_opener:
            opener=captain
            captain=None
        if opener is None:
            opener=owned_members[0]
        else:
            opener=_text(opener,f"地下城预设 {key}.opener")
        if opener not in owned_members:
            raise AetherConfigError(f"地下城预设 {key}.opener 必须是队伍中的 owned 角色")
        if captain is not None:
            captain=_text(captain,f"地下城预设 {key}.captain")
            if captain not in owned_members:
                raise AetherConfigError(f"地下城预设 {key}.captain 必须是队伍中的 owned 角色")
        effective_captain=captain or opener
        runtime_owned=[
            member["username"]
            for member in party
            if member["kind"]=="owned" and not member["leave_after_enter"]
        ]
        if not runtime_owned:
            raise AetherConfigError(f"地下城预设 {key} 至少要保留一名 owned 角色")
        if effective_captain not in runtime_owned:
            raise AetherConfigError(f"地下城预设 {key} 的实际队长不能在进入后退出")
        raw_overrides=current["event_overrides"]
        if not isinstance(raw_overrides,dict):
            raise AetherConfigError(f"地下城预设 {key}.event_overrides 必须是 object")
        event_overrides={}
        for raw_event_id,choice_index in raw_overrides.items():
            event_id=_text(raw_event_id,f"地下城预设 {key}.event_overrides key",200)
            if events is not None and event_id not in events:
                raise AetherConfigError(
                    f"地下城预设 {key} 覆写了不存在的事件：{event_id}"
                )
            if (
                isinstance(choice_index,bool)
                or not isinstance(choice_index,int)
                or not 0<=choice_index<=1000
            ):
                raise AetherConfigError(
                    f"地下城预设 {key}.event_overrides.{event_id} 必须是 0~1000"
                )
            event_overrides[event_id]=choice_index
        result[key]={
            "name":name,
            "preset_id":preset_id,
            "difficulty":difficulty,
            "party":party,
            "visibility":visibility,
            "layout_rule":layout_rule,
            "opener":opener,
            "captain":captain,
            "event_overrides":event_overrides,
        }
    return result


def load_dungeon_presets(
    *,
    owned_characters:Iterable[str],
    layout_rule_keys:Iterable[str],
    event_ids:Iterable[str]|None=None,
    path:Path|None=None,
)->dict[str,dict[str,Any]]:
    return validate_dungeon_presets(
        load_dungeon_presets_config(path),
        owned_characters=owned_characters,
        layout_rule_keys=layout_rule_keys,
        event_ids=event_ids,
    )


def save_dungeon_presets(
    value:Any,
    *,
    owned_characters:Iterable[str],
    layout_rule_keys:Iterable[str],
    dungeon_ids:Iterable[str]|None=None,
    event_ids:Iterable[str]|None=None,
    expected_keys:Iterable[str],
    path:Path|None=None,
)->dict[str,dict[str,Any]]:
    presets=validate_dungeon_presets(
        value,
        owned_characters=owned_characters,
        layout_rule_keys=layout_rule_keys,
        dungeon_ids=dungeon_ids,
        event_ids=event_ids,
        expected_keys=expected_keys,
    )
    save_json_atomic(path or dungeon_presets_path(),{"version":VERSION,"presets":presets})
    return presets
