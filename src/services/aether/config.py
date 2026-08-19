import os
from pathlib import Path

# ============================================================
# Aether 自动打本 - 用户配置
#
# 这个文件专门放“你自己的配置”。
# 以后更新主程序 Aether自动打本.py 时，原则上不需要替换本文件。
# ============================================================


# =========================
# Bot 运行参数
# =========================

# Cookie 等运行数据放 data/aether，不写进 src。
AETHER_DATA_DIR = Path(os.getenv("AETHER_DATA_DIR", "data/aether"))

# Bot 模式下 Cookie 失效时不会等待终端输入。
# 请在部署环境设置 AETHER_PASSWORD；Cookie 正常时不会使用它。
AETHER_PASSWORD_ENV = "AETHER_PASSWORD"

# Aether QQ 指令默认只允许 NoneBot SUPERUSER 调用。
AETHER_COMMAND_SUPERUSER_ONLY = True


# =========================
# 常用参数
# =========================

CAMP_STAY_TIME = 10

# 账号只保存用户名；密码仍由主程序运行时统一询问，
# 不要把密码明文写进这里。
ACCOUNT_USERNAMES = (
    "de3BDJMH",
    "Mugen",
    "Sasaki Miyo",
)


# =========================
# 副本名称
# =========================

PRESET_NAMES = {
    "beginner": "侵蚀废墟",
    "deep": "侵蚀废墟深处",
    "withered_forest": "枯萎密林",
    "living_stone": "活石矿脉",
    "cognition_garden": "认知晶庭",
    "red_leaf_canyon": "红叶山谷",
}


# =========================
# 事件 / 分支策略
# =========================

# event_id -> (事件名, 选项下标)
EVENT_CHOICES = {
    "baili_mark": ("白璃的记号", 0),
    "mirror_core": ("破碎的镜像核心", 1),
    "resonance_vein": ("共鸣晶脉", 0),
    "overloaded_runestone": ("过载的符文石", 0),
    "aether_crystal": ("神秘的以太结晶", 1),
    "abandoned_supply_box": ("废弃的补给箱", 0),
    "old_armory": ("旧时代的军械架", 0),
    "underground_spring": ("纯净的地下泉眼", 0),
    "comrade_relic": ("同类的遗物", 0),
    "scrapped_sentinel": ("报废的机械哨卫", 0),
    "abyss_whisper": ("深渊低语", 1),
    "lonely_traveler": ("孤独的旅行者", 0),
    "crackling_root": ("噼啪作响的树根", 0),
    "ancient_carving": ("古老的树皮刻文", 1),
    "lost_traveler_camp": ("迷途旅者的营地", 0),
    "burning_vine_wall": ("燃烧的藤蔓墙", 0),
    "fallen_bark_pile": ("堆积的树皮", 0),
    "sap_stream": ("树液溪流", 0),
    "strangled_bones": ("藤蔓缠骨", 0),
    "spore_cloud": ("孢子云团", 0),
    "electric_mushroom_ring": ("电蘑菇阵", 0),
    "singing_wind": ("歌声般的风", 0),
    "forest_fog": ("密林迷雾", 1),
    "bark_workshop": ("遗弃的简陋工坊", 0),
    "battle_journal": ("遗弃的战场笔记", 0),
    "dormant_repair_array": ("休眠的修复阵列", 0),
    "corrosion_fog": ("腐蚀毒雾", 0),
    "vine_cocoon": ("藤蔓茧房", 0),
    "withered_altar": ("枯萎的祭坛", 0),
    "overgrown_path": ("迷途荆棘", 0),
    "abandoned_woodcutters_camp": ("废弃的伐木营地", 0),
    "dying_embers": ("未熄灭的余烬", 0),
    "twisted_reflection": ("扭曲的倒影", 0),
    "dried_spring": ("干涸的泉眼", 0),
}

# preset_id -> 分支选项下标
BRANCH_CHOICES = {
    "deep": 1,
    "red_leaf_canyon": 1,
}

# 遇到这些 battle_preset 时直接撤离。
# 目前为空，即 Boss 正常打。
RETREAT_BATTLE_PRESETS: set[str] = set()


# =========================
# 商店购买策略
# =========================

# 当前策略：
# - 二星：买
# - 四星：买
# - 三星：买，但技能书除外
SHOP_BUY_ALWAYS_CONTAINS = (
    "（★★）",
    "（★★★★）",
)

SHOP_BUY_THREE_STAR_MARKER = "（★★★）"
SHOP_BUY_THREE_STAR_EXCLUDES = (
    "技能书",
)


# =========================
# 搜索阶段布局评分
# =========================
#
# min_score=None：
#   人工筛图，每次搜索后询问 y / n / q。
#
# min_score=数值：
#   自动筛图，分数达到阈值即接受；
#   max_attempts 控制最多生成多少张图。
#
# node_weights 只看 search 返回的 node_type。
# event / shop 的具体内容在搜索阶段不可见，所以这里写的是该副本的期望价值。
#
# 数字只是当前示例，请按你的实际收益经验长期修改。
DUNGEON_LAYOUT_RULES = {
    "beginner": {
        "node_weights": {
            "battle": 10,
            "shop": 0,
            "event": -2,
            "camp": -4,
            "treasure": 2,
            "elite": 0,
            "boss": 0,
            "boss_treasure": 0,
            "branch": 0,
        },
        "min_score": 40,
        "max_attempts": 10,
        "accept_last_on_exhausted": True,
    },
    "deep": {
        "node_weights": {
            "battle": 10,
            "shop": 0,
            "event": -4,
            "camp": -4,
            "treasure": 2,
            "elite": 0,
            "boss": 0,
            "boss_treasure": 0,
            "branch": 0,
        },
        "min_score": 22,
        "max_attempts": 20,
        "accept_last_on_exhausted": True,
    },
    "withered_forest": {
        "node_weights": {
            "battle": 10,
            "shop": 0,
            "event": 6,
            "camp": -4,
            "treasure": 2,
            "elite": 0,
            "boss": 0,
            "boss_treasure": 0,
            "branch": 0,
        },
        "min_score": 50,
        "max_attempts": 20,
        "accept_last_on_exhausted": True,
    },
    "living_stone": {
        "node_weights": {
            "battle": 10,
            "shop": 4,
            "event": 2,
            "camp": -2,
            "treasure": 2,
            "elite": 0,
            "boss": 0,
            "boss_treasure": 0,
            "branch": 0,
        },
        "min_score": 38,
        "max_attempts": 25,
        "accept_last_on_exhausted": True,
    },
    "cognition_garden": {
        "node_weights": {
            "battle": 10,
            "shop": 0,
            "event": 0,
            "camp": 0,
            "treasure": 2,
            "elite": 0,
            "boss": 0,
            "boss_treasure": 0,
            "branch": 0,
        },
        "min_score": 0,
        "max_attempts": 1,
        "accept_last_on_exhausted": True,
    },
    "red_leaf_canyon": {
        "node_weights": {
            "battle": 10,
            "shop": 0,
            "event": -4,
            "camp": 0,
            "treasure": 2,
            "elite": 0,
            "boss": 0,
            "boss_treasure": 0,
            "branch": 0,
        },
        "min_score": 24,
        "max_attempts": 50,
        "accept_last_on_exhausted": True,
    },
}


# =========================
# 地下城运行预设
# =========================
#
# 一个预设 = 一次独立运行。
# 启动脚本后先选择预设，本次只打这一个本，不会自动继续下一个。
#
# key 是稳定标识，未来 QQ Bot 直接使用它。
# name 只是展示名，可随时修改。
#
# layout_rule 指向上面的 DUNGEON_LAYOUT_RULES。
# 同一个副本可以建多个预设，例如：
#   red_leaf_money
#   red_leaf_material
DUNGEON_PRESETS = {
    #寝室废墟
    "beginner_extreme": {
        "name": "侵蚀废墟 · 极难",
        "preset_id": "beginner",
        "difficulty": "极难",
        "party": (
            ("de3BDJMH", 1),
            ("Mugen", 2),
            ("Sasaki Miyo", 0),
        ),
        "visibility": "private",
        "layout_rule": "beginner",
    },
    #深处
    "deep_extreme": {
        "name": "侵蚀废墟深处 · 极难",
        "preset_id": "deep",
        "difficulty": "极难",
        "party": (
            ("de3BDJMH", 1),
            ("Mugen", 2),
            ("Sasaki Miyo", 0),
        ),
        "visibility": "private",
        "layout_rule": "deep",
    },
    #密林
    "withered_forest_extreme": {
        "name": "枯萎密林 · 极难",
        "preset_id": "withered_forest",
        "difficulty": "极难",
        "party": (
            ("de3BDJMH", 1),
            ("Mugen", 2),
            ("Sasaki Miyo", 0),
        ),
        "visibility": "private",
        "layout_rule": "withered_forest",
    },
    #活石
    "living_stone_extreme": {
        "name": "活石矿脉 · 极难",
        "preset_id": "living_stone",
        "difficulty": "极难",
        "party": (
            ("de3BDJMH", 1),
            ("Mugen", 2),
            ("Sasaki Miyo", 0),
        ),
        "visibility": "private",
        "layout_rule": "living_stone",
    },
    #晶庭
    "cognition_garden": {
        "name": "认知晶庭",
        "preset_id": "cognition_garden",
        "difficulty": "普通",
        "party": (
            ("Sasaki Miyo", 0),
            ("de3BDJMH", 1),
            ("Mugen", 1),
        ),
        "visibility": "private",
        "layout_rule": "cognition_garden",
    },
    #红叶
    "red_leaf_extreme": {
        "name": "红叶山谷 · 极难",
        "preset_id": "red_leaf_canyon",
        "difficulty": "极难",
        "party": (
            ("Sasaki Miyo", 0),
            ("Mugen", 1),
            ("de3BDJMH", 1),
        ),
        "visibility": "private",
        "layout_rule": "red_leaf_canyon",
    },
}

NTFY_TOPIC = "de3BDJMH-Aether"