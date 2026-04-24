import json
import pathlib

from ..tools import *

ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent
DATA_PATH=ROOT_PATH/"data"/"pluginmanage"

PLUGIN_ALIAS_PATH=DATA_PATH/"plugin_alias.json"

def getPluginName(alias:str) -> str :
    """将插件别名转换为插件名"""
    plugin_alias=jsonLoad(PLUGIN_ALIAS_PATH)
    fit=""
    for pa in plugin_alias:
        if alias in plugin_alias[pa]:
            fit=pa
            break
    return fit

def getPluginDisplayName(plugin_name:str):
    """获取插件的展示名字"""
    if not (ROOT_PATH/"data"/plugin_name/"MG.json").exists():
        return plugin_name
    plugin_config=jsonLoad(ROOT_PATH/"data"/plugin_name/"MG.json")
    if plugin_config["display_name"]:
        return plugin_config["display_name"]
    else:
        return plugin_name
    