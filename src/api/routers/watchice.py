from fastapi import APIRouter,Header,HTTPException,Query
from fastapi.responses import FileResponse
from fastapi import UploadFile,File

import tempfile
import shutil
from pathlib import Path
from typing import Literal

from src.api.schemas.watchice import *
from src.services import watchice as service


router=APIRouter(prefix="/api/watchice",tags=["watchice"])

def _parse_viewer_qq(value:str|None)->int|None:
    """解析Web传入的QQ号"""

    if value is None or not value.isdigit():
        return None

    return int(value)


@router.get("/members",response_model=list[WatchiceMember])
def get_members(x_mugen_viewer_qq:str|None=Header(default=None)):
    """获取当前用户可见的群友列表"""

    viewer_qq=None

    if x_mugen_viewer_qq and x_mugen_viewer_qq.isdigit():
        viewer_qq=int(x_mugen_viewer_qq)

    return service.get_members(viewer_qq)

@router.get("/members/{slug}/images",response_model=WatchiceImageList)
def get_member_images(
    slug:str,
    page:int=Query(1,ge=1),
    page_size:int=Query(10,ge=1,le=50),
    sort:Literal["latest","oldest"]="latest",
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    """获取指定群友的图片列表"""

    viewer_qq=None

    if x_mugen_viewer_qq and x_mugen_viewer_qq.isdigit():
        viewer_qq=int(x_mugen_viewer_qq)

    result=service.get_images(
        slug,
        viewer_qq,
        page,
        page_size,
        sort
    )

    # 不存在和无权访问统一返回404
    if result is None:
        raise HTTPException(status_code=404,detail="Member not found")

    return result

@router.get("/images/{image_id}/content")
def get_image_content(
    image_id:int,
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    """获取图片内容"""

    viewer_qq=None

    if x_mugen_viewer_qq and x_mugen_viewer_qq.isdigit():
        viewer_qq=int(x_mugen_viewer_qq)

    result=service.get_image_content(image_id,viewer_qq)

    # 图片不存在和无权访问统一404
    if result is None:
        raise HTTPException(status_code=404,detail="Image not found")

    return FileResponse(
        result["path"],
        media_type=result["image"]["mime_type"]
    )

@router.post(
    "/images/{image_id}/comments",
    response_model=WatchiceComment,
    summary="发表评论"
)
def create_comment(
    image_id:int,
    body:CommentCreateRequest,
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    try:
        comment=service.add_comment(
            image_id,
            viewer_qq,
            body.content
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid comment content"
        )

    if comment is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    comment["can_delete"]=True
    return comment

@router.delete(
    "/comments/{comment_id}",
    summary="删除评论"
)
def delete_comment(
    comment_id:int,
    x_mugen_viewer_qq:str|None=Header(default=None)
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    try:
        result=service.remove_comment(
            comment_id,
            viewer_qq
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete this comment"
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    return {
        "success":True
    }

@router.get(
    "/images/{image_id}/community",
    response_model=CommunityResponse,
    summary="获取图片社区数据"
)
def get_community(
    image_id:int,
    page:int=Query(default=1,ge=1),
    page_size:int=Query(default=20,ge=1,le=50),
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    data=service.get_community(
        image_id,
        viewer_qq,
        page,
        page_size
    )

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return data

@router.put(
    "/images/{image_id}/rating",
    response_model=RatingSummary,
    summary="设置图片评分"
)
def set_rating(
    image_id:int,
    body:RatingRequest,
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    try:
        result=service.set_rating(
            image_id,
            viewer_qq,
            body.score
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid score"
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return result

@router.delete(
    "/images/{image_id}/rating",
    response_model=RatingSummary,
    summary="取消图片评分"
)
def delete_rating(
    image_id:int,
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    if viewer_qq is None:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    result=service.remove_rating(
        image_id,
        viewer_qq
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return result

@router.get(
    "/images/random",
    response_model=WatchiceRandomImageList,
    summary="随机获取可见图片"
)
def get_random_images(
    count: int = Query(
        default=1,
        ge=1,
        le=10
    ),
    member_slug: str | None = Query(
        default=None,
        min_length=1,
        max_length=100
    ),
    exclude_ids: list[int] | None = Query(
        default=None
    ),
    x_mugen_viewer_qq: str | None = Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    """
    随机返回当前用户有权查看的图片。

    - count：本次希望返回的图片数量
    - member_slug：只从指定分类中选择
    - exclude_ids：尽量避开最近看过的图片
    """

    viewer_qq = _parse_viewer_qq(
        x_mugen_viewer_qq
    )

    result = service.get_random_images(
        viewer_qq=viewer_qq,
        member_slug=member_slug,
        exclude_ids=exclude_ids,
        count=count
    )

    if not result["images"]:
        # 分类不存在、无权访问和没有图片统一返回 404，
        # 防止探测受限分类。
        raise HTTPException(
            status_code=404,
            detail="No visible image found"
        )

    return result

@router.get(
    "/admin/members",
    response_model=list[WatchiceAdminMember],
    summary="管理员获取members列表"
)
def get_admin_members(x_mugen_viewer_qq:str|None=Header(default=None)):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    members=service.get_admin_members(viewer_qq)
    if members is None:
        raise HTTPException(
            status_code=403,
            detail="Admin Required"
        )

    return members

@router.put(
    "/admin/members/{slug}/access",
    summary="设置群友权限"
)
def set_member_access(
    slug:str,
    body:MemberAccessRequest,
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    try:
        result=service.set_member_access(viewer_qq,slug,body.visibility,body.allowed_qqs)
        if not result:
            raise HTTPException(
                status_code=403,
                detail="Admin Required"
            )
    except ValueError as e:
        if str(e)=="member_not_found":
            raise HTTPException(
                status_code=404,
                detail="Member not found"
            )
        raise HTTPException(
            status_code=404,
            detail="Value Error"
        )

    return result

@router.put(
    "/admin/images/{image_id}/access",
    summary="设置图片权限"
)
def set_image_access(
    image_id:int,
    body:ImageAccessRequest,
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    try:
        result=service.set_image_access(
            viewer_qq,
            image_id,
            body.visibility,
            body.allowed_qqs
        )

        if not result:
            raise HTTPException(
                status_code=403,
                detail="Admin required"
            )

    except ValueError as e:
        if str(e)=="image_not_found":
            raise HTTPException(
                status_code=404,
                detail="Image not found"
            )
        raise

    return {
        "success":True
    }

@router.get(
    "/admin/images/{image_id}/access",
    response_model=ImageAccessResponse,
    summary="获取图片权限"
)
def get_image_access(
    image_id:int,
    x_mugen_viewer_qq:str|None=Header(
        default=None,
        alias="X-Mugen-Viewer-QQ"
    )
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)

    try:
        result=service.get_image_access(
            viewer_qq,
            image_id
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Admin required"
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return result

@router.get("/images/{image_id}/preview")
def get_image_preview(
    image_id: int,
    x_mugen_viewer_qq: str | None = Header(default=None)
):
    viewer_qq = None

    if x_mugen_viewer_qq and x_mugen_viewer_qq.isdigit():
        viewer_qq = int(x_mugen_viewer_qq)

    result = service.get_image_preview(image_id, viewer_qq)

    if result is None:
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(
        result["path"],
        media_type=result["mime_type"],
        headers={
            "Cache-Control": "private, max-age=86400"
        }
    )

@router.post("/members/{slug}/images",summary="上传图片")
async def upload_image(
    slug:str,
    file:UploadFile=File(...),
    x_mugen_viewer_qq:str|None=Header(default=None,alias="X-Mugen-Viewer-QQ")
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)
    if viewer_qq is None:
        raise HTTPException(status_code=401,detail="Login required")

    tmp_path=None

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path=Path(tmp.name)
            size=0

            while chunk:=await file.read(1024*1024):
                size+=len(chunk)

                if size>service.MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413,detail="File too large")

                tmp.write(chunk)

        try:
            return service.upload_image(slug,tmp_path,viewer_qq)
        except ValueError as e:
            if str(e)=="member_not_found":
                raise HTTPException(status_code=404,detail="Member not found")
            if str(e)=="file_too_large":
                raise HTTPException(status_code=413,detail="File too large")
            if str(e)=="duplicate_image":
                raise HTTPException(status_code=409,detail="Duplicate image")
            if str(e)=="image_too_large":
                raise HTTPException(status_code=400,detail="Image dimensions too large")
            if str(e)=="invalid_image":
                raise HTTPException(status_code=400,detail="Invalid image")
            raise
    finally:
        await file.close()
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

@router.delete("/images/{image_id}",summary="删除图片")
def delete_image(
    image_id:int,
    x_mugen_viewer_qq:str|None=Header(default=None,alias="X-Mugen-Viewer-QQ")
):
    viewer_qq=_parse_viewer_qq(x_mugen_viewer_qq)
    if viewer_qq is None:
        raise HTTPException(status_code=401,detail="Login required")

    try:
        result=service.delete_image(viewer_qq,image_id)
    except PermissionError:
        raise HTTPException(status_code=403,detail="Cannot delete this image")

    if not result:
        raise HTTPException(status_code=404,detail="Image not found")

    return {"success":True}