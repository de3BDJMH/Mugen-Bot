from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class ControlRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    action:Literal["start","pause","recover","retry","skip"]
    plan_key:str|None=Field(default=None,min_length=1,max_length=100)
    run_mode:Literal["save","balanced","rush"]="save"
    sequence:int|None=Field(default=None,ge=1,strict=True)
    run_id:str|None=Field(default=None,min_length=1,max_length=100)

    @model_validator(mode="after")
    def validate_action(self):
        if self.action=="start" and not self.plan_key:
            raise ValueError("请选择任务计划")
        if self.action in {"retry","skip"} and self.sequence is None:
            raise ValueError("请选择任务编号")
        if self.action in {"retry","skip"} and not self.run_id:
            raise ValueError("缺少批次标识，请刷新页面")
        return self


class ControlResponse(BaseModel):
    ok:bool
    message:str


class NotificationSettings(BaseModel):
    model_config=ConfigDict(extra="forbid")
    level:Literal["silent","errors","summary","detailed"]="summary"
    qq_recipients:list[str]=Field(default_factory=list,max_length=20)
