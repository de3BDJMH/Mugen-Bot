from nonebot import get_plugin_config,get_driver
from nonebot.plugin import PluginMetadata

from ...libraries.tools import *
from ...api import setup_api
from ...services.wordcloud import prepare_snapshot_cache

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="PluginAPI",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

TAG="pluginapi"
MGPLUGIN=MGPlugin(TAG)

setup_api()#注册所有API

driver=get_driver()

@driver.on_startup#检查词云快照
async def prepare_wordcloud_cache():
    prepare_snapshot_cache()