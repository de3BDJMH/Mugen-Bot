import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers.watchice import router
from src.storage import watchice as storage


app=FastAPI()
app.include_router(router)
client=TestClient(app)


@pytest.fixture
def admin_db(tmp_path,monkeypatch):
    db_path=tmp_path/"watchice.db"
    monkeypatch.setattr(storage,"DB_PATH",db_path)

    storage.init_database()

    conn=storage._connect()
    cursor=conn.cursor()

    cursor.executemany(
        """
        INSERT INTO members(slug,visibility)
        VALUES(?,?)
        """,
        [
            ("public_member","public"),
            ("private_member","allowlist")
        ]
    )

    cursor.executemany(
        """
        INSERT INTO member_aliases(member_slug,alias)
        VALUES(?,?)
        """,
        [
            ("public_member","公开群友"),
            ("private_member","私有群友")
        ]
    )

    cursor.executemany(
        """
        INSERT INTO images(
            member_slug,
            legacy_id,
            relative_path,
            visibility,
            status
        )
        VALUES(?,?,?,?,?)
        """,
        [
            (
                "public_member",
                1,
                "img/public_member/1.jpg",
                "inherit",
                "active"
            ),
            (
                "private_member",
                1,
                "img/private_member/1.jpg",
                "inherit",
                "active"
            )
        ]
    )

    cursor.executemany(
        """
        INSERT INTO member_allowed_users(member_slug,user_qq)
        VALUES(?,?)
        """,
        [
            ("private_member",111),
            ("private_member",222)
        ]
    )

    conn.commit()
    conn.close()

    return db_path

def test_admin_get_all_members(admin_db):
    response=client.get(
        "/api/watchice/admin/members",
        headers={
            "X-Mugen-Viewer-QQ":"2404164262"
        }
    )

    assert response.status_code==200

    data=response.json()
    slugs=[member["slug"] for member in data]

    assert "public_member" in slugs
    assert "private_member" in slugs

def test_non_admin_cannot_use_admin_api(admin_db):
    response=client.get(
        "/api/watchice/admin/members",
        headers={
            "X-Mugen-Viewer-QQ":"123456"
        }
    )

    assert response.status_code==403

def test_update_member_access(admin_db):
    result=storage.set_member_access(
        "public_member",
        "authenticated",
        []
    )

    assert result is True

    conn=storage._connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT visibility
        FROM members
        WHERE slug=?
        """,
        ("public_member",)
    )

    visibility=cursor.fetchone()[0]

    conn.close()

    assert visibility=="authenticated"

def test_replace_member_allowlist(admin_db):
    storage.set_member_access(
        "private_member",
        "allowlist",
        [333,444]
    )

    conn=storage._connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT user_qq
        FROM member_allowed_users
        WHERE member_slug=?
        ORDER BY user_qq
        """,
        ("private_member",)
    )

    allowed_qqs=[
        row[0]
        for row in cursor.fetchall()
    ]

    conn.close()

    assert allowed_qqs==[333,444]

def test_update_image_access(admin_db):
    conn=storage._connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT image_id
        FROM images
        WHERE member_slug=?
        """,
        ("public_member",)
    )

    image_id=cursor.fetchone()[0]
    conn.close()

    storage.set_image_access(
        image_id,
        "allowlist",
        [555,666]
    )

    conn=storage._connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT visibility
        FROM images
        WHERE image_id=?
        """,
        (image_id,)
    )
    visibility=cursor.fetchone()[0]

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

    assert visibility=="allowlist"
    assert allowed_qqs==[555,666]

def test_member_access_rollback(admin_db):
    with pytest.raises(sqlite3.IntegrityError):
        storage.set_member_access(
            "private_member",
            "authenticated",
            [333,333]
        )

    conn=storage._connect()
    cursor=conn.cursor()

    cursor.execute(
        """
        SELECT visibility
        FROM members
        WHERE slug=?
        """,
        ("private_member",)
    )
    visibility=cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT user_qq
        FROM member_allowed_users
        WHERE member_slug=?
        ORDER BY user_qq
        """,
        ("private_member",)
    )

    allowed_qqs=[
        row[0]
        for row in cursor.fetchall()
    ]

    conn.close()

    assert visibility=="allowlist"
    assert allowed_qqs==[111,222]