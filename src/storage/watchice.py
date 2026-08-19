import sqlite3
import pathlib
import json
import shutil
from PIL import Image,UnidentifiedImageError
import hashlib
from datetime import datetime


DATA_PATH=pathlib.Path(__file__).resolve().parent.parent.parent/"data"/"watchice"
DB_PATH=DATA_PATH/"database"/"watchice.db"
MEMBER_ALIAS_PATH=DATA_PATH/"member_alias.json"
IMG_PATH=DATA_PATH/"img"

def _connect()->sqlite3.Connection:
    conn=sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    return conn


def init_database():
    """初始化看群友数据库"""

    # 确保 database 文件夹存在
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)

    conn=_connect()
    cursor=conn.cursor()

    # SQLite 默认不启用外键约束，需要手动开启
    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.executescript("""
        -- 群友基础信息
        -- slug 为群友唯一标识，例如 icy、hulexy
        CREATE TABLE IF NOT EXISTS members(
            slug TEXT PRIMARY KEY,

            -- public / authenticated / allowlist
            visibility TEXT NOT NULL DEFAULT 'public',

            -- 是否启用该群友，预留给以后隐藏或停用
            enabled INTEGER NOT NULL DEFAULT 1
        );

        -- 群友别名
        -- 一个群友可以对应多个别名
        CREATE TABLE IF NOT EXISTS member_aliases(
            member_slug TEXT NOT NULL,

            -- COLLATE NOCASE 使英文别名查询时忽略大小写
            alias TEXT NOT NULL COLLATE NOCASE,

            PRIMARY KEY(member_slug,alias),

            -- 不允许两个不同群友拥有同一个别名
            UNIQUE(alias),

            FOREIGN KEY(member_slug) REFERENCES members(slug)
        );

        -- 图片索引
        -- 图片文件本身仍保存在原有文件夹中，数据库只保存其信息
        CREATE TABLE IF NOT EXISTS images(
            -- 新的全局唯一图片 ID
            -- Web、评论、评分、未来抽卡都使用它
            image_id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- 图片属于哪个群友
            member_slug TEXT NOT NULL,

            -- 原 Bot 使用的局部图片 ID
            -- 例如 icy 的第 123 张图
            legacy_id INTEGER NOT NULL,

            -- 相对于 watchice 数据目录的图片路径
            relative_path TEXT NOT NULL,

            -- 图片真实 MIME，例如 image/jpeg
            mime_type TEXT,

            width INTEGER,
            height INTEGER,

            -- 文件大小，单位字节
            file_size INTEGER,

            -- 文件 SHA-256，用于以后检测重复图片
            sha256 TEXT,

            -- 是否为 GIF / 动态 WebP 等动图
            is_animated INTEGER,

            -- 上传时间
            -- 旧图片迁移时暂时使用文件修改时间
            uploaded_at TEXT,

            -- 上传者 QQ
            -- 旧图片没有数据时可以为空
            uploader_qq INTEGER,

            -- inherit / authenticated / allowlist
            -- inherit 表示继承群友本身的权限
            visibility TEXT NOT NULL DEFAULT 'inherit',

            -- active / deleted
            -- 删除图片时以后只标记 deleted，保留 image_id
            status TEXT NOT NULL DEFAULT 'active',

            -- 同一个群友的旧 ID 不允许重复
            UNIQUE(member_slug,legacy_id),

            FOREIGN KEY(member_slug) REFERENCES members(slug)
        );

        -- 群友级 allowlist
        -- 当 members.visibility=allowlist 时使用
        CREATE TABLE IF NOT EXISTS member_allowed_users(
            member_slug TEXT NOT NULL,
            user_qq INTEGER NOT NULL,

            PRIMARY KEY(member_slug,user_qq),

            FOREIGN KEY(member_slug) REFERENCES members(slug)
        );

        -- 单张图片级 allowlist
        -- 当 images.visibility=allowlist 时使用
        CREATE TABLE IF NOT EXISTS image_allowed_users(
            image_id INTEGER NOT NULL,
            user_qq INTEGER NOT NULL,

            PRIMARY KEY(image_id,user_qq),

            FOREIGN KEY(image_id) REFERENCES images(image_id)
        );

        -- 图片列表最常用的查询：
        -- 根据群友查其 active 图片，因此提前建立索引
        CREATE INDEX IF NOT EXISTS idx_images_member
        ON images(member_slug,status);
        CREATE INDEX IF NOT EXISTS idx_images_member_sha256
        ON images(member_slug,sha256,status);
    """)

    conn.commit()
    conn.close()
init_database()

def sync_members():
    """将旧版群友与别名同步到数据库"""

    with open(MEMBER_ALIAS_PATH,encoding="utf-8") as f:
        member_alias=json.load(f)

    conn=_connect()
    cursor=conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    for slug,aliases in member_alias.items():

        # icy 暂时默认限制访问，其余群友默认公开
        visibility="allowlist" if slug=="icy" else "public"

        # 群友已存在时不重复创建
        cursor.execute(
            """
            INSERT OR IGNORE INTO members(slug,visibility)
            VALUES(?,?)
            """,
            (slug,visibility)
        )

        # 同步该群友的所有别名
        for alias in aliases:
            cursor.execute(
                """
                INSERT OR IGNORE INTO member_aliases(member_slug,alias)
                VALUES(?,?)
                """,
                (slug,alias)
            )

    conn.commit()
    conn.close()
#sync_members()

def get_member_by_alias(alias:str)->str|None:
    """根据群友别名获取slug，不存在时返回None"""

    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT member_slug
        FROM member_aliases
        WHERE alias=?
        """,
        (alias,)
    )

    row=cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def get_members()->list[dict]:
    """获取全部群友基础信息"""

    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT slug,visibility,enabled
        FROM members
        ORDER BY slug
        """
    )

    members=[
        {
            "slug":row[0],
            "visibility":row[1],
            "enabled":bool(row[2])
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return members

def create_member(slug:str,aliases:list[str])->None:
    """创建一个群友"""
    conn=_connect()
    cursor=conn.cursor()

    try:
        cursor.execute("BEGIN")

        #创建群友
        cursor.execute(
            """
            INSERT INTO members (slug,visibility,enabled)
            VALUES (?,?,?)
            """,
            (slug,"authenticated",True)
        )
        #创建别名
        cursor.executemany(
            """
            INSERT INTO member_aliases (member_slug,alias)
            VALUES (?,?)
            """,
            [(slug,alias) for alias in aliases]
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def get_member_state(slug:str)->dict|None:
    """获取指定群友的状态"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT visibility,enabled
        FROM members
        WHERE slug=?
        """,
        (slug,)
    )
    row=cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "slug": slug,
        "visibility": row[0],
        "enabled": row[1]
    }

def set_member_enabled(slug:str,enabled:bool)->bool:
    """设置群友启用状态"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        UPDATE members
        SET enabled=?
        WHERE slug=?
        """,
        (enabled,slug)
    )

    success=cursor.rowcount>0
    conn.commit()
    conn.close()

    return success

def get_alias_set()->dict:
    """获取所有人的别名"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT member_slug,alias
        FROM member_aliases
        ORDER BY member_slug,alias
        """
    )
    rows=cursor.fetchall()
    alias_set={}
    for slug,alias in rows:
        alias_set.setdefault(slug,[]).append(alias)

    return alias_set

def get_image_metadata(file:pathlib.Path)->dict|None:
    """读取图片真实信息，后缀名、长宽、是否为动图等信息"""

    try:
        with Image.open(file) as image:
            mime_type=Image.MIME.get(image.format)
            suffix_map={
                "JPEG":".jpg",
                "PNG":".png",
                "GIF":".gif",
                "WEBP":".webp"
            }
            suffix=suffix_map.get(image.format)

            if suffix is None:
                return None

            width,height=image.size
            is_animated=bool(getattr(image,"is_animated",False))
            image.verify()
    except (UnidentifiedImageError,OSError):
        return None

    # 计算文件SHA256
    sha256=hashlib.sha256()
    with open(file,"rb") as f:
        while chunk:=f.read(1024*1024):
            sha256.update(chunk)

    stat=file.stat()

    return {
        "mime_type":mime_type,
        "suffix":suffix,
        "width":width,
        "height":height,
        "file_size":stat.st_size,
        "sha256":sha256.hexdigest(),
        "is_animated":is_animated,
        "uploaded_at":datetime.fromtimestamp(stat.st_mtime).isoformat()
    }

def scan_image_files()->list[dict]:
    """扫描现有看群友图片文件"""

    images=[]

    for member in get_members():
        slug=member["slug"]
        path=IMG_PATH/slug
        if not path.exists():
            continue

        for file in path.iterdir():
            if not file.is_file():
                continue
            # 旧版图片文件名应为数字ID，例如 123.jpg
            try:
                legacy_id=int(file.stem)
            except ValueError:
                continue

            metadata=get_image_metadata(file)
            if metadata is None:# 不是有效图片就跳过
                continue
            images.append({
                "member_slug":slug,
                "legacy_id":legacy_id,
                "relative_path":file.relative_to(DATA_PATH).as_posix(),
                **metadata
            })

    return images

def sync_images():
    """将现有图片文件同步到数据库"""

    images=scan_image_files()

    conn=_connect()
    cursor=conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    for image in images:
        cursor.execute(
            """
            INSERT INTO images(
                member_slug,
                legacy_id,
                relative_path,
                mime_type,
                width,
                height,
                file_size,
                sha256,
                is_animated,
                uploaded_at
            )
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(member_slug,legacy_id)
            DO UPDATE SET
                relative_path=excluded.relative_path,
                mime_type=excluded.mime_type,
                width=excluded.width,
                height=excluded.height,
                file_size=excluded.file_size,
                sha256=excluded.sha256,
                is_animated=excluded.is_animated,
                uploaded_at=excluded.uploaded_at,
                status='active'
            """,
            (
                image["member_slug"],
                image["legacy_id"],
                image["relative_path"],
                image["mime_type"],
                image["width"],
                image["height"],
                image["file_size"],
                image["sha256"],
                image["is_animated"],
                image["uploaded_at"]
            )
        )
    # 检查数据库中的图片文件是否仍然存在
    cursor.execute(
        """
        SELECT image_id,relative_path
        FROM images
        WHERE status='active'
        """
    )

    for image_id,relative_path in cursor.fetchall():
        file=DATA_PATH/relative_path

        # 文件已经不存在，只标记删除，不删除数据库记录
        if not file.is_file():
            cursor.execute(
                """
                UPDATE images
                SET status='deleted'
                WHERE image_id=?
                """,
                (image_id,)
            )

    conn.commit()
    conn.close()
#sync_images()

def sync_library():
    """同步看群友图库"""
    sync_members()
    sync_images()
#sync_library()
#同步用这个

def check_visibility(visibility:str,viewer_qq:int|None,allowed:bool=False,is_admin:bool=False)->bool:
    """判断用户是否通过一层可见性权限"""

    # 管理员始终允许访问
    if is_admin:
        return True

    # 所有人可见
    if visibility=="public":
        return True

    # 必须登录
    if visibility=="authenticated":
        return viewer_qq is not None

    # 必须登录且位于白名单
    if visibility=="allowlist":
        return viewer_qq is not None and allowed

    # 遇到未知权限类型时默认拒绝
    return False

def can_view_member(slug:str,viewer_qq:int|None,is_admin:bool=False)->bool:
    """判断用户是否可以查看指定群友"""

    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT visibility,enabled
        FROM members
        WHERE slug=?
        """,
        (slug,)
    )

    member=cursor.fetchone()

    # 群友不存在或已停用
    if member is None or not member[1]:
        conn.close()
        return False

    visibility=member[0]
    allowed=False

    # 只有allowlist权限才需要查询白名单
    if visibility=="allowlist" and viewer_qq is not None:
        cursor.execute(
            """
            SELECT 1
            FROM member_allowed_users
            WHERE member_slug=? AND user_qq=?
            """,
            (slug,viewer_qq)
        )

        allowed=cursor.fetchone() is not None

    conn.close()

    return check_visibility(
        visibility,
        viewer_qq,
        allowed,
        is_admin
    )

def check_image_visibility(visibility:str,viewer_qq:int|None,allowed:bool=False,is_admin:bool=False)->bool:
    """判断用户是否通过图片本身的可见性权限"""

    if is_admin:
        return True

    # inherit表示图片不增加额外限制
    if visibility=="inherit":
        return True

    if visibility=="authenticated":
        return viewer_qq is not None

    if visibility=="allowlist":
        return viewer_qq is not None and allowed

    # 未知权限默认拒绝
    return False

def can_view_image(image_id:int,viewer_qq:int|None,is_admin:bool=False)->bool:
    """判断用户是否可以查看指定图片"""

    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT member_slug,visibility,status
        FROM images
        WHERE image_id=?
        """,
        (image_id,)
    )

    image=cursor.fetchone()

    # 图片不存在或已删除
    if image is None or image[2]!="active":
        conn.close()
        return False

    member_slug=image[0]
    visibility=image[1]

    # 第一层：群友权限
    if not can_view_member(member_slug,viewer_qq,is_admin):
        conn.close()
        return False

    allowed=False

    # 第二层：图片自己的白名单
    if visibility=="allowlist" and viewer_qq is not None:
        cursor.execute(
            """
            SELECT 1
            FROM image_allowed_users
            WHERE image_id=? AND user_qq=?
            """,
            (image_id,viewer_qq)
        )

        allowed=cursor.fetchone() is not None

    conn.close()

    return check_image_visibility(
        visibility,
        viewer_qq,
        allowed,
        is_admin
    )

def get_visible_members(viewer_qq:int|None,is_admin:bool=False)->list[dict]:
    """获取当前用户可见的群友"""

    conn=_connect()
    cursor=conn.cursor()

    # 先筛选当前用户能够看到的群友
    cursor.execute(
        """
        SELECT slug,visibility
        FROM members
        WHERE enabled=1
        AND (
            ?=1
            OR visibility='public'
            OR (
                visibility='authenticated'
                AND ? IS NOT NULL
            )
            OR (
                visibility='allowlist'
                AND ? IS NOT NULL
                AND EXISTS(
                    SELECT 1
                    FROM member_allowed_users
                    WHERE member_slug=members.slug
                    AND user_qq=?
                )
            )
        )
        ORDER BY slug
        """,
        (is_admin,viewer_qq,viewer_qq,viewer_qq)
    )

    rows=cursor.fetchall()

    if not rows:
        conn.close()
        return []

    slugs=[row[0] for row in rows]
    placeholders=",".join("?" for _ in slugs)

    # 一次性查询这些群友的所有别名，避免逐个查询
    cursor.execute(
        f"""
        SELECT member_slug,alias
        FROM member_aliases
        WHERE member_slug IN ({placeholders})
        ORDER BY member_slug,alias
        """,
        slugs
    )

    aliases={slug:[] for slug in slugs}

    for slug,alias in cursor.fetchall():
        aliases[slug].append(alias)

    # 一次性统计当前用户真正有权限查看的图片数量
    cursor.execute(
        f"""
        SELECT member_slug,COUNT(*)
        FROM images
        WHERE status='active'
        AND member_slug IN ({placeholders})
        AND (
            ?=1
            OR visibility='inherit'
            OR (
                visibility='authenticated'
                AND ? IS NOT NULL
            )
            OR (
                visibility='allowlist'
                AND ? IS NOT NULL
                AND EXISTS(
                    SELECT 1
                    FROM image_allowed_users
                    WHERE image_id=images.image_id
                    AND user_qq=?
                )
            )
        )
        GROUP BY member_slug
        """,
        (*slugs,is_admin,viewer_qq,viewer_qq,viewer_qq)
    )

    image_counts=dict(cursor.fetchall())

    members=[
        {
            "slug":slug,
            "visibility":visibility,
            "aliases":aliases.get(slug,[]),
            "image_count":image_counts.get(slug,0)
        }
        for slug,visibility in rows
    ]

    conn.close()
    return members

def get_visible_images(
    slug:str,
    viewer_qq:int|None,
    is_admin:bool=False,
    page:int=1,
    page_size:int=10,
    sort:str="latest"
)->dict|None:
    """获取当前用户可见的群友图片"""

    # 第一层：群友本身必须可见
    if not can_view_member(slug,viewer_qq,is_admin):
        return None

    # 防止非法分页参数
    page=max(page,1)
    page_size=max(1,min(page_size,50))
    offset=(page-1)*page_size

    conn=_connect()
    cursor=conn.cursor()

    # 图片自身的权限条件
    permission_sql="""
        (
            ?=1
            OR i.visibility='inherit'
            OR (
                i.visibility='authenticated'
                AND ? IS NOT NULL
            )
            OR (
                i.visibility='allowlist'
                AND ? IS NOT NULL
                AND EXISTS(
                    SELECT 1
                    FROM image_allowed_users AS iau
                    WHERE iau.image_id=i.image_id
                    AND iau.user_qq=?
                )
            )
        )
    """

    permission_params=(
        is_admin,
        viewer_qq,
        viewer_qq,
        viewer_qq
    )

    # 先统计当前用户实际可见的图片总数
    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM images AS i
        WHERE i.member_slug=?
        AND i.status='active'
        AND {permission_sql}
        """,
        (slug,*permission_params)
    )

    total=cursor.fetchone()[0]
    order="ASC" if sort=="oldest" else "DESC"

    # 再只取当前这一页
    cursor.execute(
        f"""
        SELECT
            i.image_id,
            i.member_slug,
            i.mime_type,
            i.width,
            i.height,
            i.is_animated,
            i.uploaded_at
        FROM images AS i
        WHERE i.member_slug=?
        AND i.status='active'
        AND {permission_sql}
        ORDER BY i.image_id {order}
        LIMIT ? OFFSET ?
        """,
        (
            slug,
            *permission_params,
            page_size,
            offset
        )
    )

    images=[
        {
            "image_id":row[0],
            "member_slug":row[1],
            "mime_type":row[2],
            "width":row[3],
            "height":row[4],
            "is_animated":bool(row[5]),
            "uploaded_at":row[6]
        }
        for row in cursor.fetchall()
    ]

    conn.close()

    return {
        "page":page,
        "page_size":page_size,
        "total":total,
        "images":images
    }

def get_all_visible_images(slug:str,viewer_qq:int|None,is_admin:bool=False)->dict[int,int]|None:
    """获取该用户可见的所有该群友图片"""
    if not can_view_member(slug,viewer_qq,is_admin):
        return None

    conn=_connect()
    cursor=conn.cursor()

    permission_sql="""
        (
            ?=1
            OR i.visibility='inherit'
            OR (
                i.visibility='authenticated'
                AND ? IS NOT NULL
            )
            OR (
                i.visibility='allowlist'
                AND ? IS NOT NULL
                AND EXISTS(
                    SELECT 1
                    FROM image_allowed_users AS iau
                    WHERE iau.image_id=i.image_id
                    AND iau.user_qq=?
                )
            )
        )
    """

    permission_params=(
        is_admin,
        viewer_qq,
        viewer_qq,
        viewer_qq
    )

    cursor.execute(
        f"""
        SELECT i.image_id,i.legacy_id
        FROM images AS i
        WHERE i.member_slug=?
        AND i.status='active'
        AND {permission_sql}
        """,
        (slug,*permission_params)
    )
    image_ids={row[1]:row[0] for row in cursor.fetchall()}

    conn.close()
    return image_ids

def get_latest_image(slug:str)->dict|None:
    """获取该群友最后一次上传的图片，包括已删除图片"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT image_id,legacy_id,status
        FROM images
        WHERE member_slug=?
        ORDER BY legacy_id DESC
        LIMIT 1
        """,
        (slug,)
    )

    row=cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "image_id":row[0],
        "legacy_id":row[1],
        "status":row[2]
    }

def get_image(image_id:int)->dict|None:
    """获取图片记录"""

    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT
            image_id,
            member_slug,
            legacy_id,
            relative_path,
            mime_type,
            width,
            height,
            file_size,
            sha256,
            is_animated,
            uploaded_at,
            uploader_qq,
            visibility,
            status
        FROM images
        WHERE image_id=?
        """,
        (image_id,)
    )

    row=cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "image_id":row[0],
        "member_slug":row[1],
        "legacy_id":row[2],
        "relative_path":row[3],
        "mime_type":row[4],
        "width":row[5],
        "height":row[6],
        "file_size":row[7],
        "sha256":row[8],
        "is_animated":row[9],
        "uploaded_at":row[10],
        "uploader_qq":row[11],
        "visibility":row[12],
        "status":row[13]
    }

MAX_IMAGE_SIDE=12000
MAX_IMAGE_PIXELS=50_000_000
def save_image(slug:str,file:pathlib.Path,uploader_qq:int)->int:
    """保存新图片并创建数据库记录"""
    file=pathlib.Path(file)
    metadata=get_image_metadata(file)
    if metadata is None:
        raise ValueError("invalid_image")
    if metadata["width"]>MAX_IMAGE_SIDE or metadata["height"]>MAX_IMAGE_SIDE or metadata["width"]*metadata["height"]>MAX_IMAGE_PIXELS:
        raise ValueError("image_too_large")
    
    target_dir=IMG_PATH/slug
    target_dir.mkdir(parents=True,exist_ok=True)

    conn=_connect()
    cursor=conn.cursor()
    target_path=None

    try:
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT image_id
            FROM images
            WHERE member_slug=?
            AND sha256=?
            AND status='active'
            LIMIT 1
            """,
            (slug,metadata["sha256"])
        )

        if cursor.fetchone() is not None:
            raise ValueError("duplicate_image")

        cursor.execute(
            """
            SELECT COALESCE(MAX(legacy_id),0)+1
            FROM images
            WHERE member_slug=?
            """,
            (slug,)
        )
        legacy_id=cursor.fetchone()[0]

        target_path=target_dir/f"{legacy_id}{metadata['suffix']}"
        relative_path=target_path.relative_to(DATA_PATH).as_posix()

        shutil.copy2(file,target_path)

        cursor.execute(
            """
            INSERT INTO images(
                member_slug,
                legacy_id,
                relative_path,
                mime_type,
                width,
                height,
                file_size,
                sha256,
                is_animated,
                uploaded_at,
                uploader_qq
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                slug,
                legacy_id,
                relative_path,
                metadata["mime_type"],
                metadata["width"],
                metadata["height"],
                metadata["file_size"],
                metadata["sha256"],
                metadata["is_animated"],
                datetime.now().isoformat(timespec="seconds"),
                uploader_qq
            )
        )

        image_id=cursor.lastrowid
        conn.commit()
        return image_id

    except Exception:
        conn.rollback()
        if target_path is not None and target_path.exists():
            target_path.unlink()
        raise

    finally:
        conn.close()

def set_image_state(image_id:int,status:str)->None:
    """设置一张图片的状态"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        UPDATE images
        SET status=?
        WHERE image_id=?
        """,
        (status,image_id,)
    )
    conn.commit()
    conn.close()

#评论评分
def init_community_tables():
    """初始化图片评分与评论表"""

    conn=_connect()
    cursor=conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS ratings(
            image_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY(image_id,user_id),
            FOREIGN KEY(image_id) REFERENCES images(image_id)
        );

        CREATE TABLE IF NOT EXISTS comments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'visible',

            FOREIGN KEY(image_id) REFERENCES images(image_id)
        );
    """)

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_comments_image_status_time
        ON comments(image_id,status,created_at DESC,id DESC)
        """
    )

    conn.commit()
    conn.close()
init_community_tables()

def create_comment(image_id:int,user_id:int,content:str,created_at:datetime)->int:
    """创建评论"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        INSERT INTO comments(
            image_id,user_id,content,created_at
        )
        VALUES(?,?,?,?)
        """,
        (
            image_id,
            user_id,
            content,
            created_at.isoformat(timespec="seconds")
        )
    )
    comment_id=cursor.lastrowid

    conn.commit()
    conn.close()

    return comment_id

def get_comment(comment_id:int)->dict|None:
    """获取评论"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT id,image_id,user_id,content,created_at,status
        FROM comments
        WHERE id=?
        AND status='visible'
        """,
        (comment_id,)
    )

    row=cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id":row[0],
        "image_id":row[1],
        "user_id":row[2],
        "content":row[3],
        "created_at":datetime.fromisoformat(row[4]),
        "status":row[5]
    }

def get_image_comments(image_id:int,page:int=1,page_size:int=20)->list[dict]:
    """获取一张图的全部评论"""
    conn=_connect()
    cursor=conn.cursor()
    
    cursor.execute(
        """
        SELECT id,image_id,user_id,content,created_at,status
        FROM comments
        WHERE image_id=?
        AND status='visible'
        ORDER BY created_at DESC,id DESC
        LIMIT ? OFFSET ?
        """,
        (
            image_id,
            page_size,
            (page-1)*page_size
        )
    )
    rows=cursor.fetchall()

    conn.close()

    return [
        {
            "id":row[0],
            "user_id":row[2],
            "content":row[3],
            "created_at":datetime.fromisoformat(row[4])
        }
        for row in rows
    ]

def delete_comment(comment_id:int)->bool:
    """删除评论"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        UPDATE comments
        SET status='deleted'
        WHERE id=?
        AND status='visible'
        """,
        (comment_id,)
    )

    changed=cursor.rowcount>0

    conn.commit()
    conn.close()

    return changed

def get_image_comment_count(image_id:int)->int:
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM comments
        WHERE image_id=?
        AND status='visible'
        """,
        (image_id,)
    )

    count=cursor.fetchone()[0]
    conn.close()

    return count

def set_image_rating(image_id:int,user_id:int,score:int,rated_at:datetime)->None:
    """设置图片评分"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        INSERT INTO ratings(
            image_id,user_id,score,created_at,updated_at
        )
        VALUES(?,?,?,?,?)
        ON CONFLICT(image_id,user_id)
        DO UPDATE SET
            score=excluded.score,
            updated_at=excluded.updated_at
        """,
        (
            image_id,
            user_id,
            score,
            rated_at.isoformat(timespec="seconds"),
            rated_at.isoformat(timespec="seconds")
        )
    )

    conn.commit()
    conn.close()

def get_user_rating(image_id:int,user_id:int)->int|None:
    """获取用户对图片的评分"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT score
        FROM ratings
        WHERE image_id=?
        AND user_id=?
        """,
        (image_id,user_id)
    )

    row=cursor.fetchone()
    conn.close()

    return row[0] if row else None

def delete_image_rating(image_id:int,user_id:int)->bool:
    """取消图片评分"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        DELETE FROM ratings
        WHERE image_id=?
        AND user_id=?
        """,
        (image_id,user_id)
    )

    changed=cursor.rowcount>0

    conn.commit()
    conn.close()

    return changed

def get_image_rating_summary(image_id:int)->dict:
    """获取图片评分汇总"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT AVG(score),COUNT(*)
        FROM ratings
        WHERE image_id=?
        """,
        (image_id,)
    )

    row=cursor.fetchone()
    average=row[0]
    count=row[1]

    cursor.execute(
        """
        SELECT score,COUNT(*)
        FROM ratings
        WHERE image_id=?
        GROUP BY score
        """,
        (image_id,)
    )

    distribution={str(i):0 for i in range(1,6)}

    for score,total in cursor.fetchall():
        distribution[str(score)]=total

    conn.close()

    return {
        "average":round(average,2) if average is not None else None,
        "count":count,
        "distribution":distribution
    }
###

def get_random_visible_images(
    viewer_qq: int | None,
    is_admin: bool = False,
    member_slug: str | None = None,
    exclude_ids: list[int] | None = None,
    count: int = 1
) -> list[dict]:
    """随机获取若干张当前用户有权查看的图片。"""

    count = max(1, min(count, 10))
    exclude_ids = list(dict.fromkeys(exclude_ids or []))[:50]

    conn = _connect()
    cursor = conn.cursor()

    conditions = [
        "m.enabled=1",
        "i.status='active'",
        """
        (
            ?=1
            OR m.visibility='public'
            OR (
                m.visibility='authenticated'
                AND ? IS NOT NULL
            )
            OR (
                m.visibility='allowlist'
                AND ? IS NOT NULL
                AND EXISTS(
                    SELECT 1
                    FROM member_allowed_users AS mau
                    WHERE mau.member_slug=m.slug
                    AND mau.user_qq=?
                )
            )
        )
        """,
        """
        (
            ?=1
            OR i.visibility='inherit'
            OR (
                i.visibility='authenticated'
                AND ? IS NOT NULL
            )
            OR (
                i.visibility='allowlist'
                AND ? IS NOT NULL
                AND EXISTS(
                    SELECT 1
                    FROM image_allowed_users AS iau
                    WHERE iau.image_id=i.image_id
                    AND iau.user_qq=?
                )
            )
        )
        """
    ]

    params: list[object] = [
        is_admin,
        viewer_qq,
        viewer_qq,
        viewer_qq,
        is_admin,
        viewer_qq,
        viewer_qq,
        viewer_qq
    ]

    if member_slug is not None:
        conditions.append("i.member_slug=?")
        params.append(member_slug)

    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        conditions.append(
            f"i.image_id NOT IN ({placeholders})"
        )
        params.extend(exclude_ids)

    where_sql = "\nAND ".join(conditions)

    cursor.execute(
        f"""
        SELECT
            i.image_id,
            i.member_slug,
            i.mime_type,
            i.width,
            i.height,
            i.is_animated,
            i.uploaded_at
        FROM images AS i
        JOIN members AS m
            ON m.slug=i.member_slug
        WHERE {where_sql}
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (*params, count)
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "image_id": row[0],
            "member_slug": row[1],
            "mime_type": row[2],
            "width": row[3],
            "height": row[4],
            "is_animated": bool(row[5]),
            "uploaded_at": row[6]
        }
        for row in rows
    ]

def get_admin_members()->list[dict]:
    """管理员列表获取"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT slug,visibility
        FROM members
        ORDER BY slug
        """
    )
    member_rows=cursor.fetchall()

    cursor.execute(
        """
        SELECT member_slug,alias
        FROM member_aliases
        ORDER BY member_slug,alias
        """
    )
    alias_rows=cursor.fetchall()

    aliases={}
    for slug,alias in alias_rows:
        aliases.setdefault(slug,[]).append(alias)

    cursor.execute(
        """
        SELECT member_slug,COUNT(*)
        FROM images
        WHERE status='active'
        GROUP BY member_slug
        """
    )
    image_rows=cursor.fetchall()
    image_counts=dict(image_rows)

    cursor.execute(
        """
        SELECT member_slug,user_qq
        FROM member_allowed_users
        ORDER BY member_slug,user_qq
        """
    )
    allowed_rows=cursor.fetchall()

    allowed_qqs={}
    for slug,user_qq in allowed_rows:
        allowed_qqs.setdefault(slug,[]).append(user_qq)

    conn.close()

    return [
        {
            "slug":slug,
            "visibility":visibility,
            "aliases":aliases.get(slug,[]),
            "image_count":image_counts.get(slug,0),
            "allowed_qqs":allowed_qqs.get(slug,[])
        }
        for slug,visibility in member_rows
    ]

def set_member_access(
    slug:str,
    visibility:str,
    allowed_qqs:list[int]
)->bool:
    allowed_qqs=list(dict.fromkeys(allowed_qqs))

    if visibility!="allowlist":
        allowed_qqs=[]
    conn=_connect()
    cursor=conn.cursor()

    try:
        cursor.execute("BEGIN")

        cursor.execute(
            """
            UPDATE members
            SET visibility=?
            WHERE slug=?
            """,
            (visibility,slug,)
        )
        if cursor.rowcount==0:
            raise ValueError("member_not_found")

        cursor.execute(
            """
            DELETE FROM member_allowed_users
            WHERE member_slug=?
            """,
            (slug,)
        )

        cursor.executemany(
            """
            INSERT INTO member_allowed_users (member_slug,user_qq)
            VALUES(?,?)
            """,
            [
                (slug,user_qq)
                for user_qq in allowed_qqs
            ]
        )

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def set_image_access(
    image_id:int,
    visibility:str,
    allowed_qqs:list[int]
)->bool:
    """设置图片权限"""
    allowed_qqs=list(dict.fromkeys(allowed_qqs))

    if visibility!="allowlist":
        allowed_qqs=[]
    conn=_connect()
    cursor=conn.cursor()

    try:
        cursor.execute("BEGIN")

        cursor.execute(
            """
            UPDATE images
            SET visibility=?
            WHERE image_id=? AND status='active'
            """,
            (visibility,image_id,)
        )

        if cursor.rowcount==0:
            raise ValueError("image_not_found")

        cursor.execute(
            """
            DELETE FROM image_allowed_users
            WHERE image_id=?
            """,
            (image_id,)
        )

        cursor.executemany(
            """
            INSERT INTO image_allowed_users(image_id,user_qq)
            VALUES(?,?)
            """,
            [
                (image_id,user_qq)
                for user_qq in allowed_qqs
            ]
        )

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def get_image_access(image_id:int)->dict|None:
    """获取图片权限设置"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT visibility
        FROM images
        WHERE image_id=? AND status='active'
        """,
        (image_id,)
    )
    row=cursor.fetchone()

    if row is None:
        conn.close()
        return None

    cursor.execute(
        """
        SELECT user_qq
        FROM image_allowed_users
        WHERE image_id=?
        ORDER BY user_qq
        """,
        (image_id,)
    )

    allowed_qqs=[
        row[0]
        for row in cursor.fetchall()
    ]

    conn.close()

    return {
        "image_id":image_id,
        "visibility":row[0],
        "allowed_qqs":allowed_qqs
    }

def get_member_aliases(slug:str)->list[str]:
    """根据slug获取该群友的所有别名"""
    conn=_connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT alias
        FROM member_aliases
        WHERE member_slug=?
        ORDER BY alias
        """,
        (slug,)
    )
    alias_rows=cursor.fetchall()
    aliases=[row[0] for row in alias_rows]

    return aliases

def set_member_aliases(slug:str,aliases:list[str]):
    """更新slug的别名"""
    conn=_connect()
    cursor=conn.cursor()

    try:
        cursor.execute("BEGIN")
        cursor.execute(
            """
            DELETE FROM member_aliases
            WHERE member_slug=?
            """,
            (slug,)
        )
        cursor.executemany(
            """
            INSERT INTO member_aliases (member_slug,alias)
            VALUES (?,?)
            """,
            [(slug,alias) for alias in aliases]
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()