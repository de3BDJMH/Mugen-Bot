import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from PIL import Image, ImageOps

from src.storage import watchice as storage

ADMIN_QQS={
    2404164262,
    2421372100
}

def is_admin(viewer_qq:int|None)->bool:
    """判断是否为看群友管理员"""

    return viewer_qq is not None and viewer_qq in ADMIN_QQS

def get_members(viewer_qq:int|None)->list[dict]:
    """获取当前用户可见的群友列表"""

    return storage.get_visible_members(
        viewer_qq,
        is_admin(viewer_qq)
    )

def create_member(slug:str,aliases:list[str])->None:
    """创建一个群友"""
    storage.create_member(slug,aliases)

def get_member_by_alias(alias:str)->str|None:
    """根据群友别名获取slug，不存在时返回None"""
    return storage.get_member_by_alias(alias)

def get_alias_set()->dict:
    """获取所有人的别名列表"""
    return storage.get_alias_set()

def get_images(
    slug:str,
    viewer_qq:int|None,
    page:int=1,
    page_size:int=10,
    sort:str="latest"
)->dict|None:
    """获取群友图片列表"""
    return storage.get_visible_images(
        slug,
        viewer_qq,
        is_admin(viewer_qq),
        page,
        page_size,
        sort
    )

def get_all_images(slug:str,viewer_qq:int|None)->dict[int,int]|None:
    """获取所有可见指定群友图片列表"""
    return storage.get_all_visible_images(slug,viewer_qq,is_admin(viewer_qq))

def get_latest_image(slug:str)->dict|None:
    return storage.get_latest_image(slug)

def _get_accessible_image(
    image_id: int,
    viewer_qq: int | None
) -> dict | None:
    admin=is_admin(viewer_qq)

    if not storage.can_view_image(image_id,viewer_qq,admin):
        return None

    image=storage.get_image(image_id)

    if image is None:
        return None

    path=storage.DATA_PATH/image["relative_path"]

    if not path.is_file():# 数据库有记录，但实际文件不存在
        return None

    return {
        "image": image,
        "path": path,
    }

def get_image_content(image_id:int,viewer_qq:int|None)->dict|None:
    """获取允许当前用户访问的图片文件信息"""
    result=_get_accessible_image(image_id, viewer_qq)

    if result is None:
        return None

    return {
        "path": result["path"],
        "image": result["image"],
    }

def upload_image(slug:str,file:Path,uploader_qq:int)->dict:
    """上传图片"""
    image_id=storage.save_image(slug,file,uploader_qq)
    return storage.get_image(image_id)

def add_comment(image_id:int,user_id:int,content:str)->dict|None:
    """发表评论"""

    if not storage.can_view_image(
        image_id,
        user_id,
        is_admin(user_id)
    ):
        return None

    content=content.strip()

    if not 1<=len(content)<=300:
        raise ValueError("invalid_content")

    created_at=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))

    comment_id=storage.create_comment(
        image_id,
        user_id,
        content,
        created_at
    )

    return storage.get_comment(comment_id)

def get_comments(
    image_id:int,
    user_id:int|None,
    page:int=1,
    page_size:int=20
)->dict|None:
    """获取图片评论"""

    admin=is_admin(user_id)

    if not storage.can_view_image(image_id,user_id,admin):
        return None

    comments=storage.get_image_comments(
        image_id,
        page,
        page_size
    )

    total=storage.get_image_comment_count(image_id)

    for comment in comments:
        comment["can_delete"]=(
            admin or
            comment["user_id"]==user_id
        )

    return {
        "page":page,
        "page_size":page_size,
        "total":total,
        "items":comments
    }

def remove_comment(comment_id:int,user_id:int)->bool|None:
    """删除评论"""

    comment=storage.get_comment(comment_id)

    if comment is None:
        return None

    admin=is_admin(user_id)

    if not storage.can_view_image(
        comment["image_id"],
        user_id,
        admin
    ):
        return None

    if not admin and comment["user_id"]!=user_id:
        raise PermissionError("cannot_delete_comment")

    return storage.delete_comment(comment_id)

def set_rating(image_id:int,user_id:int,score:int)->dict|None:
    """设置图片评分"""

    if not storage.can_view_image(
        image_id,
        user_id,
        is_admin(user_id)
    ):
        return None

    if not 1<=score<=5:
        raise ValueError("invalid_score")

    rated_at=datetime.datetime.now(ZoneInfo("Asia/Shanghai"))

    storage.set_image_rating(
        image_id,
        user_id,
        score,
        rated_at
    )

    result=storage.get_image_rating_summary(image_id)
    result["viewer_score"]=score

    return result

def remove_rating(image_id:int,user_id:int)->dict|None:
    """取消图片评分"""

    if not storage.can_view_image(
        image_id,
        user_id,
        is_admin(user_id)
    ):
        return None

    storage.delete_image_rating(image_id,user_id)

    result=storage.get_image_rating_summary(image_id)
    result["viewer_score"]=None

    return result

def get_community(
    image_id:int,
    user_id:int|None,
    page:int=1,
    page_size:int=20
)->dict|None:
    """获取图片社区数据"""

    admin=is_admin(user_id)

    if not storage.can_view_image(image_id,user_id,admin):
        return None

    rating=storage.get_image_rating_summary(image_id)

    if user_id is None:
        rating["viewer_score"]=None
    else:
        rating["viewer_score"]=storage.get_user_rating(
            image_id,
            user_id
        )

    comments=get_comments(
        image_id,
        user_id,
        page,
        page_size
    )

    if comments is None:
        return None

    return {
        "rating":rating,
        "comments":comments
    }

def get_random_images(
    viewer_qq: int | None,
    member_slug: str | None=None,
    exclude_ids: list[int] | None=None,
    count: int=1
) -> dict:
    """随机获取若干张当前用户可见的图片。"""

    count=max(1, min(count, 10))
    excluded=list(dict.fromkeys(exclude_ids or []))[:50]
    admin=is_admin(viewer_qq)

    images=storage.get_random_visible_images(
        viewer_qq=viewer_qq,
        is_admin=admin,
        member_slug=member_slug,
        exclude_ids=excluded,
        count=count
    )

    # 排除最近看过的图片后数量不足时，
    # 允许旧图片重新出现，但同一批次不重复。
    if len(images) < count and excluded:
        selected_ids=[
            image["image_id"]
            for image in images
        ]

        additional=storage.get_random_visible_images(
            viewer_qq=viewer_qq,
            is_admin=admin,
            member_slug=member_slug,
            exclude_ids=selected_ids,
            count=count - len(images)
        )

        images.extend(additional)

    return {
        "requested_count": count,
        "count": len(images),
        "images": images
    }

def get_member_state(slug:str)->dict|None:
    """获取指定群友的状态"""
    return storage.get_member_state(slug)

def set_member_enabled(user_id:int,slug:str,enabled:bool)->bool:
    """设置群友启用状态"""
    admin=is_admin(user_id)
    if not admin:
        return False
    return storage.set_member_enabled(slug,enabled)

def set_image_state(image_id:int,status:str)->None:
    """设置一张图片的状态/是否被删除"""
    storage.set_image_state(image_id,status)

def get_admin_members(user_id:int)->list[dict]|None:
    """获取管理员列表"""
    admin=is_admin(user_id)
    if not admin:
        return None

    return storage.get_admin_members()

def set_member_access(user_id:int|None,slug:str,visibility:str,allowed_qqs:list[int])->bool:
    """设置群友权限"""
    admin=is_admin(user_id)
    if not admin:
        return False

    return storage.set_member_access(slug,visibility,allowed_qqs)

def set_image_access(
    user_id:int|None,
    image_id:int,
    visibility:str,
    allowed_qqs:list[int]
)->bool:
    """设置图片权限"""
    admin=is_admin(user_id)

    if not admin:
        return False

    return storage.set_image_access(
        image_id,
        visibility,
        allowed_qqs
    )

def get_image_access(
    user_id:int|None,
    image_id:int
)->dict|None:
    """获取图片权限设置"""

    if not is_admin(user_id):
        raise PermissionError("admin_required")

    return storage.get_image_access(image_id)

def _generate_preview(source_path: Path, preview_path: Path) -> None:
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)

        # 动图取第一帧
        try:
            img.seek(0)
        except EOFError:
            pass

        # 某些模式直接存 webp 可能不稳，先转一下
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        # 最长边不超过 800
        img.thumbnail((800, 800))

        img.save(
            preview_path,
            "WEBP",
            quality=80,
            method=6,
        )

def _get_preview_path(image_id: int) -> Path:
    return storage.DATA_PATH/"_previews"/f"{image_id}.webp"

def _ensure_preview(image_id: int, source_path: Path) -> Path:
    """确保最新"""
    preview_path=_get_preview_path(image_id)
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    if not preview_path.exists():
        _generate_preview(source_path, preview_path)
        return preview_path

    source_mtime=source_path.stat().st_mtime
    preview_mtime=preview_path.stat().st_mtime

    if source_mtime > preview_mtime:
        _generate_preview(source_path, preview_path)

    return preview_path

def get_image_preview(image_id: int, viewer_qq: int | None) -> dict | None:
    result=_get_accessible_image(image_id, viewer_qq)

    if result is None:
        return None

    preview_path=_ensure_preview(image_id, result["path"])

    if not preview_path.is_file():
        return None

    return {
        "path": preview_path,
        "mime_type": "image/webp",
    }

def get_member_aliases(slug:str)->list[str]:
    """获取群友别名"""
    return storage.get_member_aliases(slug)

def set_member_aliases(slug:str,aliases:list[str]):
    """设置群友别名"""
    return storage.set_member_aliases(slug,aliases)