import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any,Iterable

from src.storage.aether import AetherConfigError,load_json_object,save_json_atomic


VERSION=1
_STRATEGY_RULES_LOCK=threading.RLock()
DOCUMENT_FIELDS={
    "preset_names",
    "event_choices",
    "branch_choices",
    "retreat_battle_presets",
    "legacy_shop",
}


@dataclass(frozen=True)
class EventChoiceRule:
    name:str
    choice_index:int


@dataclass(frozen=True)
class StrategyRules:
    preset_names:dict[str,str]
    event_choices:dict[str,EventChoiceRule]
    branch_choices:dict[str,int]
    retreat_battle_presets:tuple[str,...]
    shop_buy_always_contains:tuple[str,...]
    shop_buy_three_star_marker:str
    shop_buy_three_star_excludes:tuple[str,...]

    def payload(self)->dict[str,Any]:
        return {
            "preset_names":dict(self.preset_names),
            "event_choices":{
                event_id:{
                    "name":choice.name,
                    "choice_index":choice.choice_index,
                }
                for event_id,choice in self.event_choices.items()
            },
            "branch_choices":dict(self.branch_choices),
            "retreat_battle_presets":list(self.retreat_battle_presets),
            "legacy_shop":{
                "always_contains":list(self.shop_buy_always_contains),
                "three_star_marker":self.shop_buy_three_star_marker,
                "three_star_excludes":list(self.shop_buy_three_star_excludes),
            },
        }


def strategy_rules_path()->Path:
    from . import config as cfg

    return Path(cfg.AETHER_CONFIG_DIR)/"strategy_rules.json"


def _string(value:Any,label:str)->str:
    if not isinstance(value,str) or not value:
        raise AetherConfigError(f"{label}必须是非空字符串")
    return value


def _index(value:Any,label:str)->int:
    if isinstance(value,bool) or not isinstance(value,int) or not 0<=value<=1000:
        raise AetherConfigError(f"{label}必须是 0~1000 的整数")
    return value


def _string_list(value:Any,label:str)->tuple[str,...]:
    if not isinstance(value,list):
        raise AetherConfigError(f"{label}必须是数组")
    result=tuple(_string(item,label) for item in value)
    if len(set(result))!=len(result):
        raise AetherConfigError(f"{label}不能包含重复项")
    return result


def _string_map(value:Any,label:str)->dict[str,str]:
    if not isinstance(value,dict):
        raise AetherConfigError(f"{label}必须是 object")
    result={}
    for key,item in value.items():
        result[_string(key,f"{label} key")]=_string(item,f"{label}.{key}")
    return result


def validate_strategy_rules(
    value:Any,
    *,
    required_event_ids:Iterable[str]=(),
)->StrategyRules:
    if not isinstance(value,dict) or set(value)!=DOCUMENT_FIELDS:
        raise AetherConfigError("Aether 策略配置文件结构无效")
    event_choices=value["event_choices"]
    if not isinstance(event_choices,dict):
        raise AetherConfigError("event_choices 必须是 object")
    events={}
    for event_id,choice in event_choices.items():
        event_id=_string(event_id,"event_choices key")
        if not isinstance(choice,dict) or set(choice)!={"name","choice_index"}:
            raise AetherConfigError(f"event_choices.{event_id} 字段无效")
        events[event_id]=EventChoiceRule(
            name=_string(choice["name"],f"event_choices.{event_id}.name"),
            choice_index=_index(
                choice["choice_index"],f"event_choices.{event_id}.choice_index"
            ),
        )
    missing=set(required_event_ids)-set(events)
    if missing:
        raise AetherConfigError(
            "不能删除地下城预设正在覆写的事件：" + ", ".join(sorted(missing))
        )
    branch_choices=value["branch_choices"]
    if not isinstance(branch_choices,dict):
        raise AetherConfigError("branch_choices 必须是 object")
    branches={
        _string(preset_id,"branch_choices key"):_index(
            choice_index,f"branch_choices.{preset_id}"
        )
        for preset_id,choice_index in branch_choices.items()
    }
    legacy_shop=value["legacy_shop"]
    if not isinstance(legacy_shop,dict) or set(legacy_shop)!={
        "always_contains","three_star_marker","three_star_excludes"
    }:
        raise AetherConfigError("legacy_shop 字段无效")
    return StrategyRules(
        preset_names=_string_map(value["preset_names"],"preset_names"),
        event_choices=events,
        branch_choices=branches,
        retreat_battle_presets=_string_list(
            value["retreat_battle_presets"],"retreat_battle_presets"
        ),
        shop_buy_always_contains=_string_list(
            legacy_shop["always_contains"],"legacy_shop.always_contains"
        ),
        shop_buy_three_star_marker=_string(
            legacy_shop["three_star_marker"],"legacy_shop.three_star_marker"
        ),
        shop_buy_three_star_excludes=_string_list(
            legacy_shop["three_star_excludes"],"legacy_shop.three_star_excludes"
        ),
    )


def load_strategy_rules(path:Path|None=None)->StrategyRules:
    payload=load_json_object(path or strategy_rules_path(),label="Aether 策略配置")
    if payload.get("version")!=VERSION or set(payload)!={"version",*DOCUMENT_FIELDS}:
        raise AetherConfigError("Aether 策略配置文件结构无效")
    return validate_strategy_rules({key:payload[key] for key in DOCUMENT_FIELDS})


def save_strategy_rules(
    value:Any,
    *,
    required_event_ids:Iterable[str]=(),
    path:Path|None=None,
)->StrategyRules:
    with _STRATEGY_RULES_LOCK:
        rules=validate_strategy_rules(value,required_event_ids=required_event_ids)
        save_json_atomic(path or strategy_rules_path(),{"version":VERSION,**rules.payload()})
    return rules


def save_event_choice(
    event_id:str,
    event_name:str,
    choice_index:int,
)->EventChoiceRule:
    with _STRATEGY_RULES_LOCK:
        rules=load_strategy_rules()
        payload=rules.payload()
        payload["event_choices"][event_id]={
            "name":event_name,
            "choice_index":choice_index,
        }
        saved=save_strategy_rules(payload)
    return saved.event_choices[event_id]
