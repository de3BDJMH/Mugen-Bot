from pydantic import BaseModel,Field,ValidationError
import json
import pathlib

ROOT_PATH=pathlib.Path(__file__).parent.parent.parent.parent#/server
CONFIG_PATH=ROOT_PATH/"data"/"message_analyze"/"config.json"
CREDENTIAL_PATH=ROOT_PATH/"data"/"message_analyze"/"credentials.json"

class AIConfig(BaseModel):
    protocol:str
    base_url:str
    model:str
    credential:str
    api_key:str=Field(default="",exclude=True)

class BaseFeature(BaseModel):#默认功能配置，至少需要有这些字段，需要加字段再自己继承
    enabled:bool=False

class DailyFeature(BaseFeature):
    useAI:bool=False#是否启用ai，关闭则不会有ai总结，只有消息统计（目前仅演示，无实际功能）

class FeatureConfig(BaseModel):
    daily:DailyFeature=Field(default_factory=DailyFeature)

class GroupConfig(BaseModel):
    ai:AIConfig
    features:dict[str,FeatureConfig]=Field(default_factory=FeatureConfig)

def get_group_config(group_id:int)->GroupConfig|None:
    """读取群聊配置"""
    with open(CONFIG_PATH,encoding="utf-8") as f:
        config=json.load(f)
    group=config["groups"].get(str(group_id))
    if group is None:
        return
    ai=group.get("ai",config["default"])
    try:
        aiconfig=AIConfig.model_validate(ai)
    except ValidationError:#必要字段缺失视为无效配置群聊，但是正常不应该出现这种现象
        return
    with open(CREDENTIAL_PATH,encoding="utf-8") as f:
        credentials=json.load(f)
    aiconfig.api_key=credentials.get(aiconfig.credential,"")
    features=group.get("features",{})
    features=FeatureConfig.model_validate(features)
    group=GroupConfig(ai=aiconfig,features=features)
    return group
