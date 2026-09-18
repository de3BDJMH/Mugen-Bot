from typing import Any
import asyncio

from fastapi import APIRouter,HTTPException

from src.api.schemas.aether import (
    AetherRuntimeStatusResponse,
    DungeonPresetsRequest,
    DungeonPresetsResponse,
    StrategyRulesRequest,
    StrategyRulesResponse,
    TaskPlansRequest,
    TaskPlansResponse,
    LayoutRulesRequest,
    LayoutRulesResponse,
    RuntimeSettingsRequest,
    RuntimeSettingsResponse,
    ShopRulesRequest,
    ShopRulesResponse,
)
from src.services.aether import core
from src.services.aether.manager import aether_manager
from src.services.aether import shop_rules as service
from src.services.aether import runtime_settings
from src.services.aether import layout_rules
from src.services.aether import dungeon_presets
from src.services.aether.task_plans import load_task_plans_config
from src.services.aether import strategy_rules
from src.services.aether import task_plans
from src.services.aether import notifications
from src.api.schemas.aether_control import ControlRequest,ControlResponse,NotificationSettings


router=APIRouter(prefix="/api/aether/config",tags=["aether"])
status_router=APIRouter(prefix="/api/aether",tags=["aether"])
_control_lock=asyncio.Lock()


@status_router.post("/control",response_model=ControlResponse)
async def control_runtime(body:ControlRequest):
    async with _control_lock:
        if body.action in {"retry","skip"}:
            batch=aether_manager.status_payload().get("batch")
            if not batch or batch["run_id"]!=body.run_id:
                raise HTTPException(status_code=409,detail="任务批次已经变化，请刷新页面")
        if body.action=="start":
            ok,message=await aether_manager.start_task_plan(body.plan_key,notifications.notify_web,run_mode=body.run_mode)
        elif body.action=="recover":
            ok,message=await aether_manager.recover_task_plan(notifications.notify_web)
        elif body.action=="pause":
            ok,message=aether_manager.request_stop()
        elif aether_manager.running:
            ok,message=False,"请先暂停任务并等待当前节点完成"
        elif body.action=="retry":
            ok,message=aether_manager.retry_task(body.sequence)
        else:
            ok,message=aether_manager.skip_task(body.sequence)
    if not ok:
        raise HTTPException(status_code=409,detail=message)
    return {"ok":True,"message":message}


@router.get("/notifications",response_model=NotificationSettings)
def get_notifications():
    return notifications.load_settings()


@router.put("/notifications",response_model=NotificationSettings)
def put_notifications(body:NotificationSettings):
    try:
        return notifications.save_settings(body.model_dump())
    except notifications.AetherConfigError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc


@status_router.get("/status",response_model=AetherRuntimeStatusResponse)
def get_runtime_status():
    return aether_manager.status_payload()


def _owned_characters()->tuple[str,...]:
    usernames:list[str]=[]
    seen:set[str]=set()
    for account in core.load_accounts():
        if account.username not in seen:
            seen.add(account.username)
            usernames.append(account.username)
    for preset in core.load_dungeon_presets().values():
        for username in preset.owned_usernames:
            if username not in seen:
                seen.add(username)
                usernames.append(username)
    return tuple(usernames)


def _response_payload(characters:tuple[str,...])->dict[str,Any]:
    return service.build_shop_rules_payload(service.load_shop_rules(),characters)


@router.get("/shop-rules",response_model=ShopRulesResponse)
def get_shop_rules():
    characters=_owned_characters()
    return _response_payload(characters)


@router.put("/shop-rules",response_model=ShopRulesResponse)
def update_shop_rules(body:ShopRulesRequest):
    characters=_owned_characters()
    try:
        rules=service.save_shop_rules(
            body.default,
            body.overrides,
            body.sanity.model_dump(),
            owned_characters=characters,
        )
    except service.ShopRulesError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500,detail="商店购买策略保存失败") from exc
    return service.build_shop_rules_payload(rules,characters)


@router.get("/settings",response_model=RuntimeSettingsResponse)
def get_runtime_settings():
    try:
        return runtime_settings.load_runtime_settings().public_payload()
    except runtime_settings.AetherConfigError as exc:
        raise HTTPException(status_code=500,detail=str(exc)) from exc


@router.put("/settings",response_model=RuntimeSettingsResponse)
def update_runtime_settings(body:RuntimeSettingsRequest):
    try:
        settings=runtime_settings.save_runtime_settings(body.model_dump())
    except runtime_settings.AetherConfigError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500,detail="Aether 运行设置保存失败") from exc
    return settings.public_payload()


def _layout_references()->dict[str,list[str]]:
    result:dict[str,list[str]]={}
    for preset_key,preset in core.load_dungeon_presets().items():
        rule_key=preset.layout_rule or preset.preset_id
        result.setdefault(rule_key,[]).append(preset_key)
    return result


def _layout_payload(rules:dict[str,dict[str,Any]])->dict[str,Any]:
    references=_layout_references()
    names=strategy_rules.load_strategy_rules().preset_names
    return {
        "version":1,
        "rules":{
            key:{**rule,"name":rule.get("name") or names.get(key,key)}
            for key,rule in rules.items()
        },
        "used_by":{key:references.get(key,[]) for key in rules},
    }


@router.get("/layout-rules",response_model=LayoutRulesResponse)
def get_layout_rules():
    try:
        return _layout_payload(layout_rules.load_layout_rules())
    except layout_rules.AetherConfigError as exc:
        raise HTTPException(status_code=500,detail=str(exc)) from exc


@router.put("/layout-rules",response_model=LayoutRulesResponse)
def update_layout_rules(body:LayoutRulesRequest):
    references=_layout_references()
    try:
        rules=layout_rules.save_layout_rules(
            {key:value.model_dump() for key,value in body.rules.items()},
            required_rules=references,
        )
    except layout_rules.AetherConfigError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500,detail="Aether 布局规则保存失败") from exc
    return _layout_payload(rules)


def _preset_references()->dict[str,list[str]]:
    result:dict[str,list[str]]={}
    for plan_key,plan in load_task_plans_config().items():
        if not isinstance(plan,dict):
            continue
        for task in plan.get("tasks",[]):
            if isinstance(task,(list,tuple)) and task:
                result.setdefault(str(task[0]),[]).append(str(plan_key))
            elif isinstance(task,dict):
                preset_key=task.get("preset") or task.get("preset_key")
                if preset_key:
                    result.setdefault(str(preset_key),[]).append(str(plan_key))
    return result


def _dungeon_presets_payload(
    presets:dict[str,dict[str,Any]],
    characters:tuple[str,...],
    dungeons:dict[str,str],
    events:dict[str,str],
    rules:dict[str,dict[str,Any]],
    references:dict[str,list[str]],
)->dict[str,Any]:
    return {
        "version":1,
        "characters":list(characters),
        "dungeons":dict(dungeons),
        "events":dict(events),
        "layout_rules":list(rules),
        "presets":presets,
        "used_by":{key:references.get(key,[]) for key in presets},
    }


@router.get("/dungeon-presets",response_model=DungeonPresetsResponse)
def get_dungeon_presets():
    characters=_owned_characters()
    try:
        rules=layout_rules.load_layout_rules()
        strategy=strategy_rules.load_strategy_rules()
        dungeons=strategy.preset_names
        events={key:choice.name for key,choice in strategy.event_choices.items()}
        references=_preset_references()
        presets=dungeon_presets.load_dungeon_presets(
            owned_characters=characters,
            layout_rule_keys=rules,
            event_ids=events,
        )
        return _dungeon_presets_payload(
            presets,characters,dungeons,events,rules,references
        )
    except dungeon_presets.AetherConfigError as exc:
        raise HTTPException(status_code=500,detail=str(exc)) from exc


@router.put("/dungeon-presets",response_model=DungeonPresetsResponse)
def update_dungeon_presets(body:DungeonPresetsRequest):
    characters=_owned_characters()
    try:
        current=dungeon_presets.load_dungeon_presets_config()
        rules=layout_rules.load_layout_rules()
        strategy=strategy_rules.load_strategy_rules()
        dungeons=strategy.preset_names
        events={key:choice.name for key,choice in strategy.event_choices.items()}
        references=_preset_references()
        presets=dungeon_presets.save_dungeon_presets(
            {key:value.model_dump() for key,value in body.presets.items()},
            owned_characters=characters,
            layout_rule_keys=rules,
            dungeon_ids=dungeons,
            event_ids=events,
            expected_keys=current,
        )
    except dungeon_presets.AetherConfigError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500,detail="Aether 地下城预设保存失败") from exc
    return _dungeon_presets_payload(
        presets,characters,dungeons,events,rules,references
    )


@router.get("/strategy-rules",response_model=StrategyRulesResponse)
def get_strategy_rules():
    try:
        rules=strategy_rules.load_strategy_rules()
    except strategy_rules.AetherConfigError as exc:
        raise HTTPException(status_code=500,detail=str(exc)) from exc
    return {"version":1,**rules.payload()}


@router.put("/strategy-rules",response_model=StrategyRulesResponse)
def update_strategy_rules(body:StrategyRulesRequest):
    try:
        presets=dungeon_presets.load_dungeon_presets_config()
        required_events={
            str(event_id)
            for preset in presets.values()
            if isinstance(preset,dict)
            for event_id in preset.get("event_overrides",{})
        }
        rules=strategy_rules.save_strategy_rules(
            body.model_dump(),required_event_ids=required_events
        )
    except strategy_rules.AetherConfigError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500,detail="Aether 策略配置保存失败") from exc
    return {"version":1,**rules.payload()}


def _task_plans_payload(plans:dict[str,dict[str,Any]],presets:dict[str,core.DungeonPreset]):
    return {
        "version":1,
        "presets":{key:preset.label for key,preset in presets.items()},
        "plans":plans,
    }


@router.get("/task-plans",response_model=TaskPlansResponse)
def get_task_plans():
    try:
        presets=core.load_dungeon_presets()
        plans=task_plans.load_task_plans_config(preset_keys=presets)
    except task_plans.AetherConfigError as exc:
        raise HTTPException(status_code=500,detail=str(exc)) from exc
    return _task_plans_payload(plans,presets)


@router.put("/task-plans",response_model=TaskPlansResponse)
def update_task_plans(body:TaskPlansRequest):
    try:
        presets=core.load_dungeon_presets()
        current=task_plans.load_task_plans_config()
        plans=task_plans.save_task_plans(
            {key:value.model_dump() for key,value in body.plans.items()},
            preset_keys=presets,
            expected_keys=current,
        )
    except task_plans.AetherConfigError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500,detail="Aether 任务计划保存失败") from exc
    return _task_plans_payload(plans,presets)
