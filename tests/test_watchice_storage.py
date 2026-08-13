import sqlite3

from src.storage.watchice import *


def test_get_member_by_alias():
    assert get_member_by_alias("icy")=="icy"
    assert get_member_by_alias("冰哥")=="icy"
    assert get_member_by_alias("ICE")=="icy"
    assert get_member_by_alias("这人不存在")==None

def test_scan_image_files():
    images=scan_image_files()

    assert len(images)>0

    for image in images:
        assert image["member_slug"]
        assert isinstance(image["legacy_id"],int)
        assert image["legacy_id"]>0
        assert image["relative_path"].startswith("img/")

def test_check_visibility():
    # public
    assert check_visibility("public",None)
    assert check_visibility("public",123456)

    # authenticated
    assert not check_visibility("authenticated",None)
    assert check_visibility("authenticated",123456)

    # allowlist
    assert not check_visibility("allowlist",None)
    assert not check_visibility("allowlist",123456,False)
    assert check_visibility("allowlist",123456,True)

    # 管理员始终允许
    assert check_visibility("allowlist",123456,False,True)

    # 未知权限默认拒绝
    assert not check_visibility("???",123456)

def test_check_image_visibility():
    # inherit不增加额外限制
    assert check_image_visibility("inherit",None)

    # authenticated
    assert not check_image_visibility("authenticated",None)
    assert check_image_visibility("authenticated",123456)

    # allowlist
    assert not check_image_visibility("allowlist",None)
    assert not check_image_visibility("allowlist",123456,False)
    assert check_image_visibility("allowlist",123456,True)

    # 管理员始终允许
    assert check_image_visibility("allowlist",123456,False,True)

    # 未知权限默认拒绝
    assert not check_image_visibility("???",123456)

def test_get_visible_members():
    anonymous=get_visible_members(None)

    assert len(anonymous)>0
    assert not any(member["slug"]=="icy" for member in anonymous)

    for member in anonymous:
        assert isinstance(member["aliases"],list)
        assert isinstance(member["image_count"],int)
        assert member["image_count"]>=0

    admin=get_visible_members(123456,True)
    assert any(member["slug"]=="icy" for member in admin)

def test_pagination_boundary():
    members=get_visible_members(None)
    assert members

    slug=members[0]["slug"]

    first=get_visible_images(slug,None,page=1,page_size=1)
    assert first is not None
    assert first["page"]==1
    assert first["page_size"]==1
    assert len(first["images"])<=1

    far=get_visible_images(slug,None,page=999999,page_size=10)
    assert far is not None
    assert far["images"]==[]
    assert far["total"]==first["total"]


def test_sync_library_idempotent():
    sync_library()

    conn=sqlite3.connect(DB_PATH)
    cursor=conn.cursor()

    cursor.execute("""
        SELECT image_id,member_slug,legacy_id,status
        FROM images
        ORDER BY image_id
    """)
    before=cursor.fetchall()

    conn.close()

    sync_library()

    conn=sqlite3.connect(DB_PATH)
    cursor=conn.cursor()

    cursor.execute("""
        SELECT image_id,member_slug,legacy_id,status
        FROM images
        ORDER BY image_id
    """)
    after=cursor.fetchall()

    conn.close()

    assert before==after