from pathlib import Path
from typing import Any,Iterable

from . import config as cfg
from src.storage.aether import AetherConfigError,load_json_object,save_json_atomic


VERSION=1


def task_plans_path()->Path:
    return Path(cfg.AETHER_CONFIG_DIR)/"task_plans.json"


def _text(value:Any,label:str,max_length:int=200)->str:
    if not isinstance(value,str) or not value.strip() or len(value)>max_length:
        raise AetherConfigError(f"{label}必须是 1~{max_length} 个字符的字符串")
    return value.strip()


def _task(value:Any,label:str,preset_keys:set[str])->dict[str,Any]:
    if isinstance(value,str):
        value={"preset_key":value,"count":1,"acceleration":"auto","skip_camp_wait":True}
    elif isinstance(value,(list,tuple)):
        if not 2<=len(value)<=4:
            raise AetherConfigError(f"{label}格式无效")
        value={
            "preset_key":value[0],
            "count":value[1],
            "acceleration":value[2] if len(value)>=3 else "auto",
            "skip_camp_wait":value[3] if len(value)>=4 else True,
        }
    if not isinstance(value,dict):
        raise AetherConfigError(f"{label}必须是 object")
    current=dict(value)
    if "preset" in current and "preset_key" not in current:
        current["preset_key"]=current.pop("preset")
    current.setdefault("count",1)
    current.setdefault("acceleration","auto")
    current.setdefault("skip_camp_wait",True)
    if set(current)!={"preset_key","count","acceleration","skip_camp_wait"}:
        raise AetherConfigError(f"{label}字段无效")
    preset_key=_text(current["preset_key"],f"{label}.preset_key",100)
    if preset_key not in preset_keys:
        raise AetherConfigError(f"{label}引用了不存在的预设：{preset_key}")
    count=current["count"]
    if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=1000:
        raise AetherConfigError(f"{label}.count 必须是 1~1000")
    acceleration=current["acceleration"]
    if acceleration not in {"never","auto","always"}:
        raise AetherConfigError(f"{label}.acceleration 无效")
    skip_camp_wait=current["skip_camp_wait"]
    if not isinstance(skip_camp_wait,bool):
        raise AetherConfigError(f"{label}.skip_camp_wait 必须是 boolean")
    return {
        "preset_key":preset_key,
        "count":count,
        "acceleration":acceleration,
        "skip_camp_wait":skip_camp_wait,
    }


def validate_task_plans(
    value:Any,
    *,
    preset_keys:Iterable[str],
    expected_keys:Iterable[str]|None=None,
)->dict[str,dict[str,Any]]:
    if not isinstance(value,dict) or not 1<=len(value)<=100:
        raise AetherConfigError("Aether 任务计划必须是包含 1~100 项的 object")
    if expected_keys is not None and not set(expected_keys)<=set(value):
        raise AetherConfigError("不能删除已有任务计划")
    available=set(preset_keys)
    result={}
    for raw_key,raw in value.items():
        key=_text(raw_key,"任务计划 key",100)
        if not isinstance(raw,dict) or not {"name"}<=set(raw)<={"name","tasks","items"}:
            raise AetherConfigError(f"任务计划 {key} 字段无效")
        raw_tasks=raw.get("tasks",raw.get("items"))
        if not isinstance(raw_tasks,(list,tuple)) or not 1<=len(raw_tasks)<=500:
            raise AetherConfigError(f"任务计划 {key}.tasks 必须包含 1~500 项")
        result[key]={
            "name":_text(raw["name"],f"任务计划 {key}.name"),
            "tasks":[
                _task(task,f"任务计划 {key}.tasks[{index}]",available)
                for index,task in enumerate(raw_tasks)
            ],
        }
    return result


def load_task_plans_config(
    path:Path|None=None,
    *,
    preset_keys:Iterable[str]|None=None,
)->dict[str,Any]:
    payload=load_json_object(path or task_plans_path(),label="Aether 任务计划")
    if payload.get("version")!=VERSION or set(payload)!={"version","plans"}:
        raise AetherConfigError("Aether 任务计划文件结构无效")
    plans=payload["plans"]
    if not isinstance(plans,dict):
        raise AetherConfigError("Aether 任务计划必须是 object")
    if preset_keys is None:
        return plans
    return validate_task_plans(plans,preset_keys=preset_keys)


def save_task_plans(
    value:Any,
    *,
    preset_keys:Iterable[str],
    expected_keys:Iterable[str],
    path:Path|None=None,
)->dict[str,dict[str,Any]]:
    plans=validate_task_plans(
        value,preset_keys=preset_keys,expected_keys=expected_keys
    )
    save_json_atomic(path or task_plans_path(),{"version":VERSION,"plans":plans})
    return plans
