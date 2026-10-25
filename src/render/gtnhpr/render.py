
import base64
import datetime
import re
from pathlib import Path

from jinja2 import Environment,FileSystemLoader,select_autoescape
from nonebot_plugin_htmlrender import render_html

DIR=Path(__file__).parent
env=Environment(loader=FileSystemLoader(str(DIR)),autoescape=select_autoescape(["html","xml"]))

def parse_analysis(text:str)->dict:
    def extract(name:str)->str:
        pattern=rf"【{re.escape(name)}】\s*(.*?)(?=\n\s*【|\Z)"
        match=re.search(pattern,text,re.S)
        return match.group(1).strip() if match else ""

    return {
        "title":extract("标题"),
        "category":extract("分类"),
        "level":extract("影响等级"),
        "summary":extract("摘要"),
        "notice":extract("注意"),
        "rating":extract("AI评价"),
        "comment":extract("AI点评"),
    }

def format_merged_time(pr:dict)->str:
    merged_at=pr.get("pull_request",{}).get("merged_at") or pr.get("closed_at")
    if not merged_at:return "未知"
    dt=datetime.datetime.fromisoformat(merged_at.replace("Z","+00:00"))
    dt=dt.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
    return dt.strftime("%Y-%m-%d %H:%M")

def get_avatar()->str:
    path=DIR/"deepseek.png"
    if not path.exists():return ""
    data=base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{data}"

async def render_pr_card(pr:dict,analysis_text:str)->bytes:
    parsed=parse_analysis(analysis_text)

    level=parsed["level"] if parsed["level"] in ("高","中","低") else "低"
    level_class={"高":"high","中":"medium","低":"low"}[level]
    rating=parsed["rating"] if parsed["rating"] in ("夯","顶级","人上人","NPC","拉完了") else ""
    rating_class={
        "夯":"rating-gold",
        "顶级":"rating-green",
        "人上人":"rating-blue",
        "NPC":"rating-gray",
        "拉完了":"rating-red"
    }.get(rating,"rating-gray")

    template=env.get_template("template.html")
    html=template.render(
        repo_name=pr["repository_url"].split("/")[-1],
        pr_number=pr["number"],
        pr_title=pr["title"],
        cn_title=parsed["title"] or pr["title"],
        author=pr["user"]["login"],
        category=parsed["category"] or "未分类",
        level_text=f"{level}影响",
        level_class=level_class,
        merged_time=format_merged_time(pr),
        summary=parsed["summary"] or "暂无摘要",
        notice=parsed["notice"],
        rating=rating,
        rating_class=rating_class,
        comment=parsed["comment"],
        bot_avatar=get_avatar(),
    )
    image=await render_html(html,width=800,height=None)
    return bytes(image)
