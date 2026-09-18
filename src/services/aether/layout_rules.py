from __future__ import annotations

import re
from pathlib import Path
from typing import Any,Iterable

from . import config as cfg
from src.storage.aether import AetherConfigError,load_json_object,save_json_atomic


VERSION=1
NODE_TYPES=(
    "battle",
    "shop",
    "event",
    "camp",
    "treasure",
    "elite",
    "boss",
    "boss_treasure",
    "branch",
)
_RULE_KEY=re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def layout_rules_path()->Path:
    return Path(cfg.AETHER_CONFIG_DIR)/"layout_rules.json"


def _number(value:Any,label:str)->int|float:
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not -10000<=value<=10000:
        raise AetherConfigError(f"{label}必须是 -10000~10000 的数字")
    return value


def validate_layout_rules(
    value:Any,
    *,
    required_rules:Iterable[str]=(),
)->dict[str,dict[str,Any]]:
    if not isinstance(value,dict) or not 1<=len(value)<=100:
        raise AetherConfigError("布局规则必须是包含 1~100 项的 object")
    result={}
    for key,raw in value.items():
        if not isinstance(key,str) or _RULE_KEY.fullmatch(key) is None:
            raise AetherConfigError("布局规则 key 只能包含字母、数字、横线和下划线")
        fields={"node_weights","min_score","max_attempts","accept_last_on_exhausted"}
        if not isinstance(raw,dict) or not fields<=set(raw)<=fields|{"name"}:
            raise AetherConfigError(f"布局规则 {key} 字段无效")
        name=raw.get("name")
        if name is not None and (
            not isinstance(name,str) or not name.strip() or len(name.strip())>200
        ):
            raise AetherConfigError(f"布局规则 {key} 的 name 必须是 1~200 字符的字符串")
        weights=raw["node_weights"]
        if not isinstance(weights,dict) or set(weights)!=set(NODE_TYPES):
            raise AetherConfigError(f"布局规则 {key} 必须完整包含所有节点权重")
        min_score=raw["min_score"]
        if min_score is not None:
            min_score=_number(min_score,f"布局规则 {key} 的 min_score")
        max_attempts=raw["max_attempts"]
        if isinstance(max_attempts,bool) or not isinstance(max_attempts,int) or not 1<=max_attempts<=1000:
            raise AetherConfigError(f"布局规则 {key} 的 max_attempts 必须是 1~1000")
        accept_last=raw["accept_last_on_exhausted"]
        if not isinstance(accept_last,bool):
            raise AetherConfigError(f"布局规则 {key} 的 accept_last_on_exhausted 必须是 boolean")
        result[key]={
            "node_weights":{
                node_type:_number(weights[node_type],f"布局规则 {key} 的 {node_type}")
                for node_type in NODE_TYPES
            },
            "min_score":min_score,
            "max_attempts":max_attempts,
            "accept_last_on_exhausted":accept_last,
        }
        if name is not None:
            result[key]["name"]=name.strip()
    missing=[key for key in required_rules if key not in result]
    if missing:
        raise AetherConfigError(f"布局规则不能删除，仍有地下城预设使用：{missing[0]}")
    return result


def load_layout_rules(path:Path|None=None)->dict[str,dict[str,Any]]:
    target=path or layout_rules_path()
    payload=load_json_object(target,label="Aether 布局规则")
    if payload.get("version")!=VERSION or set(payload)!={"version","rules"}:
        raise AetherConfigError("Aether 布局规则文件结构无效")
    return validate_layout_rules(payload["rules"])


def save_layout_rules(
    value:Any,
    *,
    required_rules:Iterable[str]=(),
    path:Path|None=None,
)->dict[str,dict[str,Any]]:
    rules=validate_layout_rules(value,required_rules=required_rules)
    save_json_atomic(path or layout_rules_path(),{"version":VERSION,"rules":rules})
    return rules
