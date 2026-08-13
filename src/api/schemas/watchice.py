from pydantic import BaseModel,Field
import datetime


class WatchiceMember(BaseModel):
    slug:str
    visibility:str
    aliases:list[str]
    image_count:int

class WatchiceImage(BaseModel):
    image_id:int
    member_slug:str
    width:int|None
    height:int|None
    mime_type:str|None
    is_animated:bool
    uploaded_at:str|None


class WatchiceImageList(BaseModel):
    page:int
    page_size:int
    total:int
    images:list[WatchiceImage]

class CommentCreateRequest(BaseModel):
    content:str=Field(min_length=1,max_length=300)


class WatchiceComment(BaseModel):
    id:int
    user_id:int
    content:str
    created_at:datetime.datetime
    can_delete:bool


class CommentListResponse(BaseModel):
    page:int
    page_size:int
    total:int
    items:list[WatchiceComment]

class RatingRequest(BaseModel):
    score:int=Field(ge=1,le=5)


class RatingSummary(BaseModel):
    average:float|None
    count:int
    distribution:dict[str,int]
    viewer_score:int|None


class CommunityResponse(BaseModel):
    rating:RatingSummary
    comments:CommentListResponse