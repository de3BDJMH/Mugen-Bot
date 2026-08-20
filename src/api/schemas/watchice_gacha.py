from pydantic import BaseModel,Field
import datetime


class GachaDrawRequest(BaseModel):
    request_id:str=Field(min_length=1,max_length=100)
    count:int

class GachaDrawItem(BaseModel):
    position:int
    image_id:int
    is_new:bool
    copies_after:int

class GachaDrawResponse(BaseModel):
    draw_id:int
    count:int
    cost_base:int
    cost_addition:float
    cost_zero:bool
    created_at:datetime.datetime
    items:list[GachaDrawItem]

#收藏
class GachaCollectionItem(BaseModel):
    image_id:int
    member_slug:str
    mime_type:str|None
    width:int|None
    height:int|None
    is_animated:bool
    uploaded_at:str|None
    owned:bool
    copies:int
    first_obtained_at:datetime.datetime|None

class GachaCollectionResponse(BaseModel):
    owned_unique:int
    total_collectible:int
    items:list[GachaCollectionItem]

#历史
class GachaHistoryItem(BaseModel):
    position:int
    image_id:int
    is_new:bool
    copies_after:int

class GachaHistoryDraw(BaseModel):
    draw_id:int
    request_id:str
    count:int
    cost_base:int
    cost_addition:float
    cost_zero:bool
    created_at:datetime.datetime
    items:list[GachaHistoryItem]

class GachaHistoryResponse(BaseModel):
    page:int
    page_size:int
    total:int
    items:list[GachaHistoryDraw]

#config
class GachaCost(BaseModel):
    base:int
    addition:float
    zero:bool

class GachaConfigResponse(BaseModel):
    enabled:bool
    single_cost:GachaCost
    ten_cost:GachaCost