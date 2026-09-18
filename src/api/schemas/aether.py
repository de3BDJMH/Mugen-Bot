from typing import Annotated,Literal

from pydantic import BaseModel,ConfigDict,Field


ShopSlot=Literal["1","2","3"]
DefaultMode=Literal["never","always","legacy"]
OverrideMode=Literal["inherit","never","always","legacy"]
AetherEventChoiceIndex=Annotated[int,Field(ge=0,le=1000)]
LayoutNodeType=Literal[
    "battle",
    "shop",
    "event",
    "camp",
    "treasure",
    "elite",
    "boss",
    "boss_treasure",
    "branch",
]


class SanityRules(BaseModel):
    model_config=ConfigDict(extra="forbid")

    lower:int=Field(ge=0,le=20)
    upper:int=Field(ge=0,le=20)
    buyers:list[str]=Field(default_factory=list,max_length=100)


class ShopRulesRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    default:dict[ShopSlot,DefaultMode]=Field(min_length=3,max_length=3)
    overrides:dict[str,dict[ShopSlot,OverrideMode]]=Field(default_factory=dict,max_length=100)
    sanity:SanityRules


class ShopRulesResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")

    version:Literal[1]
    characters:list[str]
    default:dict[ShopSlot,DefaultMode]
    overrides:dict[str,dict[ShopSlot,OverrideMode]]
    effective:dict[str,dict[ShopSlot,DefaultMode]]
    sanity:SanityRules


class RuntimeSettingsRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    camp_stay_time:int=Field(ge=0,le=3600)
    acceleration_balanced_min_wait_seconds:int=Field(ge=0,le=86400)
    acceleration_ticket_reserve:int=Field(ge=0,le=1000000)
    acceleration_rush_ignore_reserve:bool
    consecutive_failure_limit:int=Field(ge=1,le=100)
    ntfy_topic:str|None=Field(default=None,max_length=200)
    ntfy_server:str=Field(min_length=1,max_length=500)
    account_usernames:list[str]=Field(min_length=1,max_length=100)
    command_superuser_only:bool


class RuntimeSettingsResponse(RuntimeSettingsRequest):
    version:Literal[1]


class LayoutRule(BaseModel):
    model_config=ConfigDict(extra="forbid")

    name:str=Field(min_length=1,max_length=200)
    node_weights:dict[LayoutNodeType,int|float]=Field(min_length=9,max_length=9)
    min_score:int|float|None=Field(default=None,ge=-10000,le=10000)
    max_attempts:int=Field(ge=1,le=1000)
    accept_last_on_exhausted:bool


class LayoutRulesRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    rules:dict[str,LayoutRule]=Field(min_length=1,max_length=100)


class LayoutRulesResponse(LayoutRulesRequest):
    version:Literal[1]
    used_by:dict[str,list[str]]


class DungeonPartyMember(BaseModel):
    model_config=ConfigDict(extra="forbid")

    username:str=Field(min_length=1,max_length=100)
    kind:Literal["owned","friend"]
    preset_index:int|None=Field(default=None,ge=0,le=4)
    leave_after_enter:bool=False


class DungeonPreset(BaseModel):
    model_config=ConfigDict(extra="forbid")

    name:str=Field(min_length=1,max_length=200)
    preset_id:str=Field(min_length=1,max_length=100)
    difficulty:Literal["简单","普通","困难","极难"]
    party:list[DungeonPartyMember]=Field(min_length=1,max_length=3)
    visibility:Literal["private","friends","public"]
    layout_rule:str=Field(min_length=1,max_length=100)
    opener:str=Field(min_length=1,max_length=100)
    captain:str|None=Field(default=None,min_length=1,max_length=100)
    event_overrides:dict[str,AetherEventChoiceIndex]=Field(default_factory=dict,max_length=100)


class DungeonPresetsRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    presets:dict[str,DungeonPreset]=Field(min_length=1,max_length=100)


class DungeonPresetsResponse(DungeonPresetsRequest):
    version:Literal[1]
    characters:list[str]
    dungeons:dict[str,str]
    events:dict[str,str]
    layout_rules:list[str]
    used_by:dict[str,list[str]]


class EventChoice(BaseModel):
    model_config=ConfigDict(extra="forbid")

    name:str=Field(min_length=1,max_length=200)
    choice_index:int=Field(ge=0,le=1000)


class LegacyShopRule(BaseModel):
    model_config=ConfigDict(extra="forbid")

    always_contains:list[str]=Field(max_length=100)
    three_star_marker:str=Field(min_length=1,max_length=100)
    three_star_excludes:list[str]=Field(max_length=100)


class StrategyRulesRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    preset_names:dict[str,str]=Field(max_length=100)
    event_choices:dict[str,EventChoice]=Field(max_length=500)
    branch_choices:dict[str,int]=Field(max_length=100)
    retreat_battle_presets:list[str]=Field(max_length=100)
    legacy_shop:LegacyShopRule


class StrategyRulesResponse(StrategyRulesRequest):
    version:Literal[1]


class TaskPlanItem(BaseModel):
    model_config=ConfigDict(extra="forbid")

    preset_key:str=Field(min_length=1,max_length=100)
    count:int=Field(ge=1,le=1000)
    acceleration:Literal["never","auto","always"]
    skip_camp_wait:bool


class TaskPlan(BaseModel):
    model_config=ConfigDict(extra="forbid")

    name:str=Field(min_length=1,max_length=200)
    tasks:list[TaskPlanItem]=Field(min_length=1,max_length=500)


class TaskPlansRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    plans:dict[str,TaskPlan]=Field(min_length=1,max_length=100)


class TaskPlansResponse(TaskPlansRequest):
    version:Literal[1]
    presets:dict[str,str]


class AetherRuntimeCounts(BaseModel):
    model_config=ConfigDict(extra="forbid")

    success:int=Field(ge=0)
    running:int=Field(ge=0)
    pending:int=Field(ge=0)
    uncertain:int=Field(ge=0)
    failed:int=Field(ge=0)
    blocked:int=Field(ge=0)
    skipped:int=Field(ge=0)
    cancelled:int=Field(ge=0)


class AetherRuntimeNode(BaseModel):
    model_config=ConfigDict(extra="forbid")

    index:int=Field(ge=0)
    node_type:LayoutNodeType


class AetherRuntimeTask(BaseModel):
    model_config=ConfigDict(extra="forbid")

    sequence:int=Field(ge=1)
    preset_key:str
    preset_label:str
    status:Literal["pending","running","success","failed","blocked","uncertain","skipped","cancelled"]
    phase:str
    node_name:str|None
    node_index:int|None
    nodes:list[AetherRuntimeNode]
    started_at:float|None
    finished_at:float|None
    error:str|None
    owned_characters:list[str]
    holds_resource_lock:bool


class AetherSingleRuntimeStatus(BaseModel):
    model_config=ConfigDict(extra="forbid")

    preset_key:str|None
    preset_label:str|None
    fast_mode:bool
    phase:str
    node_name:str|None
    node_index:int|None
    nodes:list[AetherRuntimeNode]
    started_at:float|None
    last_message:str|None
    pending_kind:Literal["layout","event","password"]|None


class AetherBatchRuntimeStatus(BaseModel):
    model_config=ConfigDict(extra="forbid")

    running:bool
    recoverable:bool
    run_id:str|None
    plan_key:str
    plan_name:str|None
    run_mode:Literal["save","balanced","rush"]
    result:Literal["unfinished","completed_with_failures","completed"]
    started_at:float|None
    finished_at:float|None
    archived_at:float|None
    last_message:str|None
    blocked_characters:list[str]
    failure_streaks:dict[str,int]
    checkpoint_loaded:bool
    checkpoint_error:str|None
    counts:AetherRuntimeCounts
    tasks:list[AetherRuntimeTask]


class AetherRuntimeStatusResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")

    version:Literal[1]
    mode:Literal["idle","single","batch"]
    running:bool
    recoverable:bool
    updated_at:float
    single:AetherSingleRuntimeStatus|None
    batch:AetherBatchRuntimeStatus|None
