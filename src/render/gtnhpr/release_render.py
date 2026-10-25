import re
from datetime import datetime,timezone,timedelta
from pathlib import Path

from jinja2 import Environment,FileSystemLoader
from nonebot_plugin_htmlrender import render_html

TEMPLATE=Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    autoescape=True
).get_template("release_template.html")


async def render_release_card(release:dict,description="",highlights=None)->bytes:
    tag=release["tag_name"]
    name=tag.lower()

    if "nightly" in name:
        release_type="Nightly"
    elif re.search(r"(^|[-_.])rc(?:[-_.]|\d|$)",name):
        release_type="RC"
    elif "beta" in name:
        release_type="Beta"
    elif "alpha" in name:
        release_type="Beta"
    else:
        release_type="Stable"

    version=tag.removeprefix("v")
    build=""

    published=release.get("published_at")
    date=datetime.fromisoformat(published.replace("Z","+00:00")).astimezone(
        timezone(timedelta(hours=8))
    ).strftime("%Y-%m-%d") if published else ""

    html=TEMPLATE.render(
        version=version,
        release_type=release_type,
        date=date,
        build=build,
        description=description or "GT New Horizons 新版本已发布。",
        highlights=highlights or []
    )

    return bytes(await render_html(
        html,
        width=1048,
        device_pixel_ratio=1
    ))
