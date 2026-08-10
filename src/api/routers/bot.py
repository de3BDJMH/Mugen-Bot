from datetime import datetime

from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot
from fastapi import APIRouter

from ..schemas import bot as schemas

router = APIRouter(
    prefix="/api/bot",
    tags=["Bot"],
)

START_TIME = datetime.now()


@router.get(
    "/status",
    response_model=schemas.BotStatusResponse,
    summary="获取 Bot 当前状态",
    description="返回 Bot 连接状态、登录信息、运行时间和 OneBot 版本。",
)
async def get_bot_status():
    bot: Bot = get_bot()

    uptime = int((datetime.now() - START_TIME).total_seconds())
    login_info = await bot.get_login_info()
    version = await bot.get_version_info()

    return schemas.BotStatusResponse(
        online=True,
        self_id=bot.self_id,
        uptime=uptime,
        login_info=schemas.LoginInfo(
            user_id=login_info["user_id"],
            nickname=login_info["nickname"],
        ),
        version=version,
    )

"""
这个页面以后可以从“在线状态页”逐渐扩展成一个轻量的 Bot 运行面板，不需要一次塞满。
我认为比较适合公开展示的有：
今日接收消息数
今日指令调用次数
当前服务群数量
今日活跃用户数，只展示汇总数字
Bot 最近一次收到消息的时间
最近一次重启时间
近 7 天在线率
指令平均响应时间
指令成功率与失败次数
当前启用插件数量
Bot 当前版本和最近更新时间
指令统计可以设计得更丰富一些：
今日最常用指令排行
最近 7 天指令调用折线图
每小时调用量分布
不同功能分类的占比
单个指令的成功、失败与平均耗时
与前一天或上周同期相比的变化
比如可以展示：
今日调用 2,431 次
较昨日 +12.4%

/phi b       684
/mai b50     391
签到         286
随机歌曲     175
运行质量方面也很有价值：
API 平均响应时间
OneBot 连接延迟
当前正在处理的任务数
消息处理队列长度
最近 24 小时异常数量
最后一次异常发生时间
最近是否发生过断线重连
服务器资源也可以展示，但建议只公开概括，不泄露机器信息：
CPU 使用率
内存使用率
Bot 进程占用内存
数据库或缓存更新时间
不要公开服务器 IP、磁盘路径、异常堆栈、群号、用户 QQ、API 地址和密钥。
页面结构以后可以形成四层：
顶部：在线状态、运行时间、版本。
概览：消息、指令、活跃用户、服务群数量。
趋势：7 天调用折线、指令排行、时段分布。
运行质量：响应时间、成功率、异常和重连情况。
下一批最值得先做的是“今日指令量、今日消息量、服务群数量、7 天指令趋势”。这些数据直观、容易理解，而且暂时不涉及复杂权限或用户隐私。等 Bot 侧开始记录耗时和执行结果后，再加入成功率与性能指标。"""