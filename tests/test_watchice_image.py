import sqlite3

import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient
from io import BytesIO

from src.api.routers.watchice import router
from src.storage import watchice as storage


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def image_db(tmp_path, monkeypatch):
    db_path = tmp_path / "watchice.db"
    data_path = tmp_path / "watchice_data"

    data_path.mkdir()

    monkeypatch.setattr(storage, "DB_PATH", db_path)
    monkeypatch.setattr(storage, "DATA_PATH", data_path)

    # 使用正式的建表逻辑
    storage.init_database()

    # 创建一张真实测试图片
    image_path = data_path / "test.jpg"
    Image.new("RGB", (1200, 600)).save(image_path, "JPEG")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # public member
    cursor.execute("""
        INSERT INTO members(slug, visibility)
        VALUES('test_member', 'public')
    """)

    # inherit -> 继承 member 的 public
    cursor.execute("""
        INSERT INTO images(
            member_slug,
            legacy_id,
            relative_path,
            mime_type,
            width,
            height,
            visibility
        )
        VALUES(
            'test_member',
            1,
            'test.jpg',
            'image/jpeg',
            1200,
            600,
            'inherit'
        )
    """)

    image_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "image_id": image_id,
        "data_path": data_path,
    }

def test_get_image_preview(image_db):
    image_id = image_db["image_id"]

    response = client.get(
        f"/api/watchice/images/{image_id}/preview"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "private, max-age=86400"
    assert len(response.content) > 0
    img = Image.open(BytesIO(response.content))

    assert img.size == (800, 400)

def test_get_image_preview_forbidden(image_db):
    image_id = image_db["image_id"]

    conn = sqlite3.connect(storage.DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE images
        SET visibility = 'allowlist'
        WHERE image_id = ?
    """, (image_id,))

    conn.commit()
    conn.close()

    response = client.get(
        f"/api/watchice/images/{image_id}/preview",
        headers={"X-Mugen-Viewer-QQ": "123456"}
    )

    assert response.status_code == 404

def test_get_image_preview_uses_cache(image_db):
    image_id = image_db["image_id"]

    response1 = client.get(
        f"/api/watchice/images/{image_id}/preview"
    )
    assert response1.status_code == 200

    preview_path = storage.DATA_PATH / "_previews" / f"{image_id}.webp"
    mtime1 = preview_path.stat().st_mtime_ns

    response2 = client.get(
        f"/api/watchice/images/{image_id}/preview"
    )
    assert response2.status_code == 200

    mtime2 = preview_path.stat().st_mtime_ns

    assert mtime2 == mtime1