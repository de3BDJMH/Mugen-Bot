from __future__ import annotations

import getpass
import json
import os
import pathlib
import pickle
import threading
import time
from dataclasses import dataclass,field
from typing import Any, Callable, Literal
from urllib.parse import quote

import requests

from . import config as cfg
from .shop_rules import (
    SanityOffer,
    ShopRules,
    effective_rule,
    is_sanity_item,
    load_shop_rules,
    sanity_recovery,
    select_sanity_purchases,
)
from .runtime_settings import RuntimeSettings,load_runtime_settings
from .layout_rules import load_layout_rules as load_layout_rules_config
from .dungeon_presets import load_dungeon_presets_config
from src.storage.aether import AetherConfigError
from .strategy_rules import StrategyRules,load_strategy_rules,save_event_choice


# =========================
# 基础配置
# =========================

BASE_URL = "https://chiyuki.diving-fish.com/api/aether"
WEB_URL = "https://chiyuki.diving-fish.com/aether/"
REQUEST_TIMEOUT = 10
PARTY_ACTION_DELAY = 0.5
PARTY_STATE_CHECK_ATTEMPTS = 10
DUNGEON_REROLL_DELAY = 2.0
BATTLE_FINISH_BUFFER = 3

# 新 OAuth / 多角色体系：
# 一个水鱼登录态，通过 query 参数选择具体 Aether 角色。
AETHER_CHARACTER_PARAM = "_aether_character"
AETHER_CHARACTER_HEADER = "X-Aether-Character"
AETHER_AUTH_COOKIE_NAME = "divingfish_aether_token"

VISIBILITY_NAMES = {
    "private": "仅自己可见",
    "friends": "好友可见",
    "public": "公开",
}

NODE_NAMES = {
    "battle": "战斗",
    "event": "事件",
    "camp": "营地",
    "shop": "商店",
    "treasure": "宝箱",
    "elite": "精英",
    "boss": "Boss",
    "boss_treasure": "Boss 宝箱",
    "branch": "分支",
}

NODE_SYMBOLS = {
    "battle": "B",
    "elite": "B",
    "boss": "B",
    "event": "E",
    "camp": "C",
    "shop": "S",
    "treasure": "x",
    "boss_treasure": "x",
    "branch": "T",
}

# API key 统一按“领域_动作”命名，避免 current / next / enter 这类含义不明的名字。
API_ENDPOINTS = {
    "login": "/login",
    "account": "/account",
    "status": "/status",
    "preset_apply": "/status/presets/apply",
    "dungeon_search": "/dungeon/search",
    "dungeon_disband": "/dungeon/disband",
    "dungeon_join": "/dungeon/join",
    "dungeon_recruit": "/dungeon/recruit",
    "dungeon_reorder": "/dungeon/reorder",
    "dungeon_current": "/dungeon/current",
    "dungeon_enter": "/dungeon/enter",
    "dungeon_transfer_leader": "/dungeon/leader/transfer",
    "dungeon_leave": "/dungeon/leave",
    "dungeon_retreat": "/dungeon/retreat",
    "node_current": "/dungeon/node",
    "node_next": "/dungeon/node/next",
    "battle_prepare": "/dungeon/node/battle/prepare",
    "battle_start": "/dungeon/node/battle/start",
    "battle_complete": "/dungeon/node/battle/complete",
    "battle_accelerate": "/dungeon/node/battle/accelerate",
    "camp_enter": "/dungeon/node/camp/enter",
    "camp_leave": "/dungeon/node/camp/leave",
    "event_choose": "/dungeon/node/event/choice",
    "treasure_open": "/dungeon/node/treasure",
    "shop_get": "/dungeon/node/shop",
    "shop_buy": "/dungeon/node/shop/buy",
    "shop_leave": "/dungeon/node/shop/leave",
    "branch_choose": "/dungeon/node/branch/choose",
}




AccelerationMode = Literal["never", "threshold", "always"]

# =========================
# 数据结构
# =========================


@dataclass(frozen=True)
class Account:
    username: str
    password: str | None = None


@dataclass(frozen=True)
class BattleStartResult:
    forced_exit: bool
    wait_time: float = 0.0
    data: dict[str, Any] | None = None


@dataclass(frozen=True)
class LayoutRule:
    """搜索阶段的节点布局评分规则。

    search 返回的 nodes 目前只包含 node_type，因此这里只按节点类型评分。
    min_score=None 表示人工筛图模式：每次显示评分后等待用户确认。
    min_score 为数值时表示自动筛图模式。
    max_attempts 只用于自动筛图；人工模式下可一直刷新，直到接受或主动终止。
    """

    node_weights: dict[str, float]
    min_score: float | None = None
    max_attempts: int = 1
    accept_last_on_exhausted: bool = True


@dataclass(frozen=True)
class LayoutCandidate:
    attempt: int
    score: float
    counts: dict[str, int]
    layout: tuple[str, ...]


@dataclass(frozen=True)
class UnknownEvent:
    event_id: str
    event_name: str
    options: tuple[str, ...]
    raw: dict[str, Any]


@dataclass
class RuntimeHooks:
    """把同步打本核心与 CLI / QQ Bot 交互解耦。

    这些回调都在打本工作线程中执行，因此 Bot 侧的实现必须线程安全。
    """

    choose_layout: Callable[[LayoutCandidate], Literal["accept", "refresh", "abort"]] | None = None
    choose_unknown_event: Callable[[UnknownEvent], int | None] | None = None
    request_password: Callable[[str], str | None] | None = None
    notify: Callable[[str], None] | None = None
    on_state: Callable[[str, dict[str, Any]], None] | None = None
    should_stop: Callable[[], bool] | None = None

    def emit(self, message: str) -> None:
        if self.notify is not None:
            self.notify(message)

    def state(self, phase: str, **data: Any) -> None:
        if self.on_state is not None:
            self.on_state(phase, data)

    def stop_requested(self) -> bool:
        return bool(self.should_stop and self.should_stop())




@dataclass(frozen=True)
class PartyMember:
    """地下城队伍成员。

    kind="owned":
        当前水鱼账号下、由 Bot 直接控制的 Aether 角色。
        preset_index 必须是 0~4。

    kind="friend":
        通过 /dungeon/recruit 作为 offline_friend 招募的离线好友。
        不需要 OAuth Client，也不参与并发资源锁。
    """

    username: str
    kind: Literal["owned", "friend"] = "owned"
    preset_index: int | None = None
    leave_after_enter:bool=False

    @property
    def controlled(self) -> bool:
        return self.kind == "owned"


@dataclass(frozen=True)
class DungeonPreset:
    """一次独立地下城运行所需的完整预设。

    party 表示进入地下城时的站位顺序，第一位允许是 offline_friend。
    opener_username 表示开本角色；captain_username 未配置时继承开本角色。
    队伍最多 3 人；离线好友可以重复出现在不同并行任务中。
    """

    key: str
    name: str
    preset_id: str
    difficulty: str
    party: tuple[PartyMember, ...]
    visibility: str = "private"
    layout_rule: str | None = None
    opener_username:str|None=None
    captain_username: str | None = None
    event_overrides:dict[str,int]=field(default_factory=dict)

    def __post_init__(self) -> None:
        owned = self.owned_members
        if not owned:
            raise ValueError(f"预设 {self.key!r} 至少需要一名自有角色担任队长")

        owned_usernames={member.username for member in owned}
        if self.opener_username is not None and self.opener_username not in owned_usernames:
            raise ValueError(f"预设 {self.key!r} 的 opener 必须是 party 中的自有角色")
        if self.captain_username is not None and self.captain_username not in owned_usernames:
            raise ValueError(f"预设 {self.key!r} 的 captain 必须是 party 中的自有角色")
        if self.leader.leave_after_enter:
            raise ValueError(f"预设 {self.key!r} 的实际队长不能在进入后退出")
        if not self.runtime_owned_members:
            raise ValueError(f"预设 {self.key!r} 至少要保留一名自有角色")

    @property
    def label(self) -> str:
        return self.name

    @property
    def leader(self) -> PartyMember:
        if self.captain_username is not None:
            for member in self.owned_members:
                if member.username == self.captain_username:
                    return member
        return self.opener

    @property
    def opener(self)->PartyMember:
        if self.opener_username is not None:
            for member in self.owned_members:
                if member.username==self.opener_username:
                    return member
        return self.owned_members[0]

    @property
    def owned_members(self) -> tuple[PartyMember, ...]:
        return tuple(member for member in self.party if member.controlled)

    @property
    def owned_usernames(self) -> tuple[str, ...]:
        return tuple(member.username for member in self.owned_members)

    @property
    def runtime_members(self)->tuple[PartyMember,...]:
        return tuple(member for member in self.party if not member.leave_after_enter)

    @property
    def runtime_owned_members(self)->tuple[PartyMember,...]:
        return tuple(member for member in self.runtime_members if member.controlled)

    @property
    def runtime_owned_usernames(self)->tuple[str,...]:
        return tuple(member.username for member in self.runtime_owned_members)

    @property
    def runtime_member_usernames(self)->tuple[str,...]:
        return tuple(member.username for member in self.runtime_members)

    @property
    def member_usernames(self) -> tuple[str, ...]:
        return tuple(member.username for member in self.party)


# =========================
# 配置加载
# =========================


def load_layout_rules() -> dict[str, LayoutRule]:
    rules: dict[str, LayoutRule] = {}

    for preset_id, raw in load_layout_rules_config().items():
        if not isinstance(raw, dict):
            raise TypeError(f"布局规则 {preset_id!r} 必须是 dict")

        weights = raw.get("node_weights", {})
        if not isinstance(weights, dict):
            raise TypeError(f"布局规则 {preset_id!r} 的 node_weights 必须是 dict")

        rules[preset_id] = LayoutRule(
            node_weights={
                str(node_type): float(weight)
                for node_type, weight in weights.items()
            },
            min_score=(
                None
                if raw.get("min_score") is None
                else float(raw["min_score"])
            ),
            max_attempts=int(raw.get("max_attempts", 1)),
            accept_last_on_exhausted=bool(
                raw.get("accept_last_on_exhausted", True)
            ),
        )

    return rules


def _parse_party(
    raw_party: object,
    *,
    context: str,
) -> tuple[PartyMember, ...]:
    if not isinstance(raw_party, (list, tuple)):
        raise TypeError(f"{context} 的 party 必须是 list/tuple")

    party: list[PartyMember] = []

    for raw_member in raw_party:
        username: str
        kind: Literal["owned", "friend"]
        preset_index: int | None
        leave_after_enter=False

        if isinstance(raw_member, dict):
            if not set(raw_member)<={
                "username","kind","preset_index","preset","leave_after_enter"
            }:
                raise TypeError(f"{context} 的 party dict 成员字段无效")
            if "username" not in raw_member:
                raise TypeError(f"{context} 的 party dict 成员缺少 username")

            username = str(raw_member["username"])
            raw_kind = str(raw_member.get("kind", "owned")).lower()

            if raw_kind in {"owned", "self", "player"}:
                kind = "owned"
            elif raw_kind in {"friend", "offline_friend", "offline"}:
                kind = "friend"
            else:
                raise ValueError(
                    f"{context}：{username} 的 kind 无效：{raw_kind!r}"
                )

            raw_preset = raw_member.get(
                "preset_index",
                raw_member.get("preset"),
            )

            if kind == "owned":
                if raw_preset is None:
                    raise ValueError(
                        f"{context}：自有角色 {username} 必须配置 preset_index"
                    )
                if isinstance(raw_preset,bool):
                    raise ValueError(f"{context}：{username} 的预设槽位不能是 boolean")
                preset_index = int(raw_preset)
            else:
                if raw_preset is not None:
                    raise ValueError(f"{context}：离线好友 {username} 不能配置预设槽位")
                preset_index = None
            leave_after_enter=raw_member.get("leave_after_enter",False)
            if not isinstance(leave_after_enter,bool):
                raise ValueError(f"{context}：{username} 的进入后退出必须是 boolean")
            if kind=="friend" and leave_after_enter:
                raise ValueError(f"{context}：离线好友 {username} 不能配置进入后退出")

        elif isinstance(raw_member, (list, tuple)):
            if len(raw_member) == 2:
                username = str(raw_member[0])
                second = raw_member[1]

                # 兼容旧格式 ("用户名", 预设槽位)。
                if isinstance(second, str) and second.lower() in {
                    "friend",
                    "offline_friend",
                    "offline",
                }:
                    kind = "friend"
                    preset_index = None
                else:
                    kind = "owned"
                    if isinstance(second,bool):
                        raise ValueError(f"{context}：{username} 的预设槽位不能是 boolean")
                    preset_index = int(second)

            elif len(raw_member) == 3:
                username = str(raw_member[0])
                raw_kind = str(raw_member[1]).lower()

                if raw_kind in {"owned", "self", "player"}:
                    kind = "owned"
                    if isinstance(raw_member[2],bool):
                        raise ValueError(f"{context}：{username} 的预设槽位不能是 boolean")
                    preset_index = int(raw_member[2])
                elif raw_kind in {"friend", "offline_friend", "offline"}:
                    if raw_member[2] is not None:
                        raise ValueError(f"{context}：离线好友 {username} 不能配置预设槽位")
                    kind = "friend"
                    preset_index = None
                else:
                    raise ValueError(
                        f"{context}：{username} 的 kind 无效：{raw_kind!r}"
                    )
            else:
                raise TypeError(
                    f"{context} 的 party tuple 必须是 "
                    "(用户名, 预设槽位)、(好友名, 'friend') "
                    "或 (用户名, kind, 预设槽位)"
                )
        else:
            raise TypeError(f"{context} 的 party 成员格式无效：{raw_member!r}")

        if not username:
            raise ValueError(f"{context} 的成员用户名不能为空")

        if kind == "owned":
            assert preset_index is not None
            if not 0 <= preset_index <= 4:
                raise ValueError(
                    f"{context}：{username} 的预设槽位必须在 0~4"
                )

        party.append(
            PartyMember(
                username=username,
                kind=kind,
                preset_index=preset_index,
                leave_after_enter=leave_after_enter,
            )
        )

    if not party:
        raise ValueError(f"{context} 的 party 不能为空")

    if len(party) > 3:
        raise ValueError(f"{context} 的 party 最多只能有 3 名成员")

    if not any(member.controlled for member in party):
        raise ValueError(f"{context} 至少需要一名自有角色担任队长")

    usernames = [member.username for member in party]
    if len(set(usernames)) != len(usernames):
        raise ValueError(f"{context} 的队伍成员重复：{usernames}")

    return tuple(party)


def load_dungeon_presets() -> dict[str, DungeonPreset]:
    """从独立配置文件读取地下城预设。"""
    raw_presets=load_dungeon_presets_config()
    layout_rules=load_layout_rules_config()
    strategy_rules=load_strategy_rules()

    if raw_presets is not None:
        if not isinstance(raw_presets, dict):
            raise TypeError("DUNGEON_PRESETS 必须是 dict")

        presets: dict[str, DungeonPreset] = {}

        for raw_key, raw in raw_presets.items():
            key = str(raw_key)

            if not isinstance(raw, dict):
                raise TypeError(f"预设 {key!r} 必须是 dict")
            if not {"preset_id","difficulty","party"}<=set(raw)<= {
                "name","preset_id","difficulty","party","visibility","layout_rule","opener","captain",
                "event_overrides"
            }:
                raise AetherConfigError(f"预设 {key!r} 字段无效")

            preset_id = str(raw["preset_id"])
            difficulty = str(raw["difficulty"])
            default_name = (
                f"{strategy_rules.preset_names.get(preset_id,preset_id)} · {difficulty}"
            )

            visibility=str(raw.get("visibility","private"))
            if visibility not in VISIBILITY_NAMES:
                raise AetherConfigError(f"预设 {key!r} 的 visibility 无效：{visibility}")
            layout_rule=(
                preset_id
                if raw.get("layout_rule") is None
                else str(raw["layout_rule"])
            )
            if layout_rule not in layout_rules:
                raise AetherConfigError(f"预设 {key!r} 引用了不存在的布局规则：{layout_rule}")
            raw_event_overrides=raw.get("event_overrides",{})
            if not isinstance(raw_event_overrides,dict):
                raise AetherConfigError(f"预设 {key!r} 的 event_overrides 必须是 object")
            event_overrides={}
            for raw_event_id,choice_index in raw_event_overrides.items():
                event_id=str(raw_event_id)
                if event_id not in strategy_rules.event_choices:
                    raise AetherConfigError(f"预设 {key!r} 覆写了不存在的事件：{event_id}")
                if (
                    isinstance(choice_index,bool)
                    or not isinstance(choice_index,int)
                    or not 0<=choice_index<=1000
                ):
                    raise AetherConfigError(
                        f"预设 {key!r} 的事件 {event_id!r} 选项下标无效"
                    )
                event_overrides[event_id]=choice_index
            party=_parse_party(raw.get("party"),context=f"预设 {key!r}")
            if "opener" in raw:
                opener_username=(
                    None if raw.get("opener") is None else str(raw["opener"])
                )
                captain_username=(
                    None if raw.get("captain") is None else str(raw["captain"])
                )
            else:
                opener_username=(
                    None if raw.get("captain") is None else str(raw["captain"])
                )
                captain_username=None
            presets[key] = DungeonPreset(
                key=key,
                name=str(raw.get("name") or default_name),
                preset_id=preset_id,
                difficulty=difficulty,
                party=party,
                visibility=visibility,
                layout_rule=layout_rule,
                opener_username=opener_username,
                captain_username=captain_username,
                event_overrides=event_overrides,
            )

        return presets

    legacy_tasks = getattr(cfg, "DUNGEON_TASKS", None)

    if not isinstance(legacy_tasks, (list, tuple)):
        raise RuntimeError(
            "配置中既没有 DUNGEON_PRESETS，"
            "也没有可兼容的 DUNGEON_TASKS"
        )

    print("检测到旧 DUNGEON_TASKS，已临时转换为独立预设")
    presets: dict[str, DungeonPreset] = {}

    for index, raw in enumerate(legacy_tasks, start=1):
        if not isinstance(raw, dict):
            raise TypeError(f"旧任务 #{index} 必须是 dict")

        preset_id = str(raw["preset_id"])
        difficulty = str(raw["difficulty"])
        key = f"legacy_{index}_{preset_id}"

        presets[key] = DungeonPreset(
            key=key,
            name=(
                f"{strategy_rules.preset_names.get(preset_id,preset_id)} · "
                f"{difficulty}"
            ),
            preset_id=preset_id,
            difficulty=difficulty,
            party=_parse_party(
                raw.get("party"),
                context=f"旧任务 #{index}",
            ),
            visibility=str(raw.get("visibility", "private")),
            layout_rule=preset_id,
            opener_username=(
                None
                if raw.get("captain") is None
                else str(raw["captain"])
            ),
        )

    return presets


DUNGEON_LAYOUT_RULES = load_layout_rules()
DUNGEON_PRESETS = load_dungeon_presets()


def reload_dungeon_presets()->dict[str,DungeonPreset]:
    presets=load_dungeon_presets()
    DUNGEON_PRESETS.clear()
    DUNGEON_PRESETS.update(presets)
    return DUNGEON_PRESETS


# =========================
# API 客户端
# =========================


class AetherClient:
    """单个 Aether 账号的 HTTP API 客户端。

    这里只负责“如何请求服务器”，不负责决定事件选什么、商店买什么、分支走哪条。
    """

    def __init__(self, account: Account, cookie_file: pathlib.Path | None = None):
        self.session = requests.Session()

        # 新账号体系下，username 表示 Aether “角色 username”，
        # 不再表示水鱼主账号登录名。
        self.username = account.username
        self.character = account.username
        self.password = account.password
        self.dungeon_id: Any | None = None
        self.last_search_result: dict[str, Any] | None = None

        # 给上层通知系统保留最近一次底层错误。
        # 不只 print 到服务器控制台，否则手机收到“推进失败”时不知道原因。
        self.last_error: str | None = None
        self.last_error_at: float = 0.0

        if cookie_file is None:
            data_dir = pathlib.Path(cfg.AETHER_DATA_DIR)
            data_dir.mkdir(parents=True, exist_ok=True)
            cookie_file = data_dir / f"{self.username}_cookies.pkl"
        self.cookie_file = cookie_file

    @staticmethod
    def _url(endpoint_name: str) -> str:
        try:
            return BASE_URL + API_ENDPOINTS[endpoint_name]
        except KeyError as exc:
            raise KeyError(f"未知 API endpoint：{endpoint_name}") from exc

    def clear_last_error(self) -> None:
        self.last_error = None
        self.last_error_at = 0.0

    def _set_last_error(self, message: str) -> None:
        # ntfy 没必要收到整页 HTML / 巨型 JSON，限制长度即可。
        message = str(message).strip()
        if len(message) > 1200:
            message = message[:1200] + "…"
        self.last_error = message
        self.last_error_at = time.time()

    @staticmethod
    def _extract_error_body(response: requests.Response) -> str:
        """优先提取 API JSON 的 message/detail，否则退回 response.text。"""
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            for key in ("message", "detail", "error"):
                value = payload.get(key)
                if value not in (None, ""):
                    return str(value)

        body = response.text.strip()
        return body or "<empty response>"

    def _request(
        self,
        method: str,
        endpoint_name: str,
        *,
        error_message: str,
        timeout: float = REQUEST_TIMEOUT,
        **kwargs: Any,
    ) -> requests.Response | None:
        """统一处理请求异常和非 2xx 响应，并保存错误给上层通知。"""
        # 当前请求开始时先清空本账号旧错误，避免把历史错误误报成当前节点错误。
        self.clear_last_error()

        endpoint = API_ENDPOINTS.get(endpoint_name, endpoint_name)
        request_label = f"{method.upper()} {endpoint}"

        # OAuth 多角色协议：
        # 浏览器实际请求同时携带：
        #   ?_aether_character=<角色>
        #   X-Aether-Character: <角色>
        #
        # Header 才是后端识别当前 active_character 的关键上下文；
        # query 参数也保留，严格跟随 Web 端协议。
        if endpoint_name != "login":
            raw_params = kwargs.pop("params", None)
            params = dict(raw_params or {})
            params.setdefault(AETHER_CHARACTER_PARAM, self.character)
            kwargs["params"] = params

            raw_headers = kwargs.pop("headers", None)
            headers = dict(raw_headers or {})
            headers.setdefault(AETHER_CHARACTER_HEADER, self.character)
            kwargs["headers"] = headers

        try:
            response = self.session.request(
                method,
                self._url(endpoint_name),
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            detail = f"{request_label} -> 网络异常：{exc}"
            self._set_last_error(detail)
            print(f"{error_message}：网络异常：{exc}")
            return None

        if not response.ok:
            body = self._extract_error_body(response)
            detail = (
                f"{request_label} -> HTTP {response.status_code}: {body}"
            )
            self._set_last_error(detail)
            print(
                f"{error_message}：状态码 {response.status_code}，"
                f"响应内容：{response.text}"
            )
            return None

        return response

    def _response_json(
        self,
        response: requests.Response,
        *,
        context: str,
    ) -> dict[str, Any] | None:
        try:
            data = response.json()
        except ValueError:
            detail = (
                f"{context}：服务器返回的不是合法 JSON："
                f"{response.text[:800]}"
            )
            self._set_last_error(detail)
            print(f"{context}：服务器返回的不是合法 JSON：{response.text}")
            return None

        if not isinstance(data, dict):
            detail = (
                f"{context}：服务器返回的数据结构异常："
                f"{type(data).__name__}"
            )
            self._set_last_error(detail)
            print(f"{context}：服务器返回的数据结构异常：{type(data).__name__}")
            return None
        return data

    def set_oauth_token(self, token: str) -> None:
        """把水鱼 OAuth 登录后的 Aether Cookie 注入当前角色 Session。"""
        token = str(token).strip()
        if not token:
            raise ValueError("OAuth token 不能为空")

        self.session.cookies.clear()
        self.session.cookies.set(
            AETHER_AUTH_COOKIE_NAME,
            token,
            domain="chiyuki.diving-fish.com",
            path="/",
        )

    def get_account_info(self) -> dict[str, Any] | None:
        """读取当前水鱼账号下的 Aether 角色列表。"""
        response = self._request(
            "GET",
            "account",
            error_message=f"{self.username} 查询 OAuth 账号信息失败",
        )
        if response is None:
            return None

        return self._response_json(
            response,
            context=f"{self.username} 查询 OAuth 账号信息失败",
        )

    def try_oauth_login(self, token: str) -> bool:
        """使用同一个水鱼 OAuth Cookie，以当前 character 身份验证。

        验证成功条件：
        1. /account 请求成功；
        2. data.active_character == 当前角色；
        3. characters 中确实存在当前角色。
        """
        try:
            self.set_oauth_token(token)
        except ValueError as exc:
            self._set_last_error(str(exc))
            return False

        result = self.get_account_info()
        if result is None:
            self.session.cookies.clear()
            return False

        data = result.get("data")
        if not isinstance(data, dict):
            self._set_last_error("OAuth /account 响应中缺少 data")
            self.session.cookies.clear()
            return False

        active_character = data.get("active_character")
        characters = data.get("characters")
        if not isinstance(characters, list):
            self._set_last_error("OAuth /account 响应中缺少 characters")
            self.session.cookies.clear()
            return False

        character_names = {
            str(item.get("username"))
            for item in characters
            if isinstance(item, dict) and item.get("username")
        }

        if self.character not in character_names:
            self._set_last_error(
                f"当前水鱼账号下没有 Aether 角色：{self.character}"
            )
            self.session.cookies.clear()
            return False

        if active_character != self.character:
            self._set_last_error(
                "OAuth 角色切换校验失败："
                f"请求 {self.character!r}，"
                f"服务器返回 active_character={active_character!r}"
            )
            self.session.cookies.clear()
            return False

        print(
            f"{self.username} OAuth 登录有效，"
            "已绑定到当前水鱼账号下的角色"
        )
        self.get_current_dungeon(silent=True)
        return True

    def _save_cookies(self) -> None:
        try:
            with self.cookie_file.open("wb") as file:
                pickle.dump(self.session.cookies, file)
        except OSError as exc:
            # Cookie 保存失败不应该让一次成功登录变成失败。
            print(f"{self.username}：Cookie 保存失败：{exc}")

    def _load_cookies(self) -> bool:
        if not self.cookie_file.exists():
            return False

        try:
            with self.cookie_file.open("rb") as file:
                cookies = pickle.load(file)
            self.session.cookies.update(cookies)
            return True
        except (OSError, pickle.PickleError, EOFError, AttributeError, TypeError):
            return False

    def _saved_session_is_valid(self) -> bool:
        try:
            response = self.session.get(
                self._url("status"),
                params={AETHER_CHARACTER_PARAM: self.character},
                headers={AETHER_CHARACTER_HEADER: self.character},
                timeout=5,
            )
            return response.ok
        except requests.RequestException:
            return False

    def try_cookie_login(self) -> bool:
        """只尝试 Cookie 登录，不触发密码输入。"""
        if not self._load_cookies():
            return False

        if not self._saved_session_is_valid():
            # 避免失效 Cookie 继续污染后续密码登录请求。
            self.session.cookies.clear()
            return False

        print(f"{self.username} Cookie 有效，直接复用登录状态")
        self.get_current_dungeon(silent=True)
        return True

    def login_with_password(self, password: str) -> bool:
        """使用密码登录，并在成功后更新 Cookie。"""
        print(f"{self.username} Cookie 无效或不存在，正在使用密码登录...")
        response = self._request(
            "POST",
            "login",
            error_message=f"{self.username} 登录失败",
            json={"username": self.username, "password": password},
        )
        if response is None:
            return False

        self.password = password
        self._save_cookies()
        self.get_current_dungeon(silent=True)
        print(f"{self.username} 登录成功，Cookie 已更新")
        return True

    def apply_preset(self, index: int) -> bool:
        """切换角色预设槽位。槽位索引范围为 0~4。"""
        if not 0 <= index <= 4:
            print(f"{self.username}：预设槽位必须在 0~4 之间，当前为 {index}")
            return False

        response = self._request(
            "POST",
            "preset_apply",
            error_message=f"{self.username} 切换预设失败",
            json={"index": index},
        )
        if response is None:
            return False

        print(f"{self.username} 已切换到预设槽位 {index}")
        return True

    def search_dungeon(
        self,
        difficulty:str,
        preset_id:str,
        visibility:str,
        display_name:str|None=None,
    )->bool:
        """搜索并创建地下城。"""
        response = self._request(
            "POST",
            "dungeon_search",
            error_message="搜索地下城失败",
            json={
                "difficulty": difficulty,
                "preset_id": preset_id,
                "visibility": visibility,
            },
        )
        if response is None:
            return False

        result = self._response_json(response, context="搜索地下城失败")
        if result is None:
            return False

        # 搜索成功时，服务器已经返回完整地下城/节点布局。
        # 这里保留下来供“候选布局检查”使用，但脚本不会自动反复重搜。
        self.last_search_result = result

        try:
            dungeon = result["data"]
            self.dungeon_id = dungeon["dungeon_id"]
            nodes = dungeon["nodes"]
            invite_code = dungeon["invite_code"]
        except (KeyError, TypeError):
            print(f"搜索地下城失败：响应结构异常：{result}")
            return False

        node_counts: dict[str, int] = {}
        node_symbols: list[str] = []
        for node in nodes:
            node_type = node.get("node_type", "unknown")
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
            node_symbols.append(NODE_SYMBOLS.get(node_type, "?"))

        node_info = "\n".join(
            f"  - {NODE_NAMES.get(node_type, node_type)}：{count}"
            for node_type, count in node_counts.items()
        )
        invite_link = f"{WEB_URL}?dungeon_id={self.dungeon_id}"

        label=display_name or f"{preset_id} · {difficulty}"
        print(
            f"{label} 搜索成功\n"
            f"可见性：{VISIBILITY_NAMES.get(visibility, visibility)}\n"
            f"花费：{result.get('cost', '?')}\n"
            f"节点：{' '.join(node_symbols)}\n"
            f"节点信息：\n{node_info}\n"
            f"邀请码：{invite_code}\n"
            f"邀请链接：{invite_link}"
        )
        return True

    def disband_dungeon(self) -> bool:
        response = self._request(
            "POST",
            "dungeon_disband",
            error_message="解散地下城失败",
        )
        if response is None:
            return False

        self.dungeon_id = None
        print("解散成功")
        return True

    def join_dungeon(self, dungeon_id: Any) -> bool:
        response = self._request(
            "POST",
            "dungeon_join",
            error_message=f"{self.username} 加入队伍失败",
            json={"dungeon_id": dungeon_id},
        )
        if response is None:
            return False

        result = self._response_json(response, context="加入队伍失败")
        if result is None:
            return False

        self.dungeon_id = dungeon_id
        leader_id = result.get("data", {}).get("leader_id", "未知队长")
        print(f"{self.username} 成功加入 {leader_id} 的队伍")
        return True

    def recruit_offline_friend(self, key: str) -> bool:
        """招募一个离线好友加入当前地下城大厅。

        Web 端已确认协议：
            POST /dungeon/recruit
            {"type": "offline_friend", "key": "<好友username>"}
        """
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "dungeon_recruit",
            error_message=f"招募离线好友 {key} 失败",
            json={
                "type": "offline_friend",
                "key": key,
            },
        )
        if response is None:
            return False

        result = self._response_json(
            response,
            context=f"招募离线好友 {key} 失败",
        )
        if result is None:
            return False

        data = result.get("data")
        if isinstance(data, dict) and data.get("dungeon_id"):
            self.dungeon_id = data["dungeon_id"]

        print(f"已招募离线好友：{key}")
        return True

    def reorder_members(self, from_index: int, to_index: int) -> bool:
        response = self._request(
            "POST",
            "dungeon_reorder",
            error_message="交换队员位置失败",
            json={"index1": from_index, "index2": to_index},
        )
        if response is None:
            return False

        print(f"{from_index} -> {to_index} 交换位置成功")
        return True

    def get_current_dungeon(self, *, silent: bool = False) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "dungeon_current",
            error_message="查询当前地下城失败",
        )
        if response is None:
            if not silent:
                self.dungeon_id = None
            return None

        result = self._response_json(response, context="查询当前地下城失败")
        if result is None:
            return None

        data = result.get("data")
        self.dungeon_id = data.get("dungeon_id") if isinstance(data, dict) else None
        return result

    def enter_dungeon(self) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "dungeon_enter",
            error_message="进入地下城失败",
        )
        if response is None:
            return False

        print("已成功进入地下城")
        return True

    def transfer_dungeon_leader(self,target_username:str)->bool:
        if not self._require_dungeon():
            return False
        response=self._request(
            "POST",
            "dungeon_transfer_leader",
            error_message=f"转移队长给 {target_username} 失败",
            json={"target_username":target_username},
        )
        if response is None:
            return False
        result=self._response_json(response,context="转移队长失败")
        if result is None:
            return False
        data=result.get("data")
        if (
            result.get("code")!=0
            or not isinstance(data,dict)
            or data.get("leader_id")!=target_username
        ):
            self._set_last_error("转移队长响应未确认新队长")
            print(f"转移队长失败：响应未确认 {target_username}")
            return False
        print(f"已将队长转移给 {target_username}")
        return True

    def leave_dungeon(self)->bool:
        if not self._require_dungeon():
            return False
        response=self._request(
            "POST",
            "dungeon_leave",
            error_message=f"{self.username} 退出地下城失败",
        )
        if response is None:
            return False
        result=self._response_json(response,context="退出地下城失败")
        if result is None:
            return False
        if result.get("code")!=0:
            self._set_last_error(str(result.get("message") or "退出地下城失败"))
            return False
        self.dungeon_id=None
        print(f"{self.username} 已退出地下城")
        return True

    def retreat_dungeon(self) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "dungeon_retreat",
            error_message="撤离地下城失败",
        )
        if response is None:
            return False

        print("地下城已撤离")
        self.dungeon_id = None
        return True

    def get_current_node(self) -> dict[str, Any] | None:
        if not self._require_dungeon():
            return None

        response = self._request(
            "GET",
            "node_current",
            error_message="查询当前节点失败",
        )
        if response is None:
            return None
        return self._response_json(response, context="查询当前节点失败")

    def next_node(self) -> dict[str, Any] | None:
        """推进到下一节点，返回 /node/next 的完整响应。

        当前前端协议会读取顶层 settlement；
        非结算状态下应再 GET /dungeon/node 获取真正的下一节点详情。
        """
        if not self._require_dungeon():
            return None

        response = self._request(
            "POST",
            "node_next",
            error_message="前往下一节点失败",
        )
        if response is None:
            return None

        print("已前往下一节点")
        return self._response_json(response, context="前往下一节点失败")

    def prepare_battle(self) -> str | None:
        """准备地下城战斗并返回 battle_id。

        当前自动打本流程默认不调用这个接口，因为服务端允许直接 start。
        保留该方法是为了让 API 封装与当前前端协议一致。
        """
        if not self._require_dungeon():
            return None

        response = self._request(
            "POST",
            "battle_prepare",
            error_message="准备战斗失败",
        )
        if response is None:
            return None

        result = self._response_json(response, context="准备战斗失败")
        if result is None:
            return None

        battle_id = result.get("data", {}).get("battle_id")
        if battle_id is None:
            print(f"准备战斗失败：响应中缺少 data.battle_id：{result}")
            return None

        return str(battle_id)

    def start_battle(self) -> BattleStartResult | None:
        """开始战斗。

        正常时返回等待秒数；如果服务器返回 forced_exit，则显式告诉 Runner，
        不再把它误判成“缺少 battle.available_at”。
        """
        if not self._require_dungeon():
            return None

        response = self._request(
            "POST",
            "battle_start",
            error_message="开始战斗失败",
        )
        if response is None:
            return None

        result = self._response_json(response, context="开始战斗失败")
        if result is None:
            return None

        if result.get("forced_exit"):
            data = result.get("data")
            if not isinstance(data, dict):
                data = None
            print("服务器强制结束了当前战斗")
            return BattleStartResult(
                forced_exit=True,
                wait_time=0.0,
                data=data,
            )

        try:
            finish_time = float(result["battle"]["available_at"])
        except (KeyError, TypeError, ValueError):
            print(f"开始战斗失败：响应中缺少 battle.available_at：{result}")
            return None

        wait_time = max(0.0, finish_time - time.time())
        print(
            "战斗已开始\n"
            f"预计结束时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(finish_time))}\n"
            f"等待时间约 {int(wait_time)} 秒"
        )
        return BattleStartResult(
            forced_exit=False,
            wait_time=wait_time,
            data=result,
        )

    def get_accel_ticket_count(self) -> int | None:
        """读取当前账号持有的地下城加速券数量。

        数据来源：
            GET /api/aether/status

        路径：
            response["data"]["backpack"]["materials"]

        目标物品：
            item_id == "dungeon_accel_ticket"

        找不到该物品时视为 0；请求或数据结构异常时返回 None。
        """
        response = self._request(
            "GET",
            "status",
            error_message=f"查询 {self.username} 加速券数量失败",
        )
        if response is None:
            return None

        result = self._response_json(
            response,
            context=f"查询 {self.username} 加速券数量失败",
        )
        if result is None:
            return None

        data = result.get("data")
        if not isinstance(data, dict):
            print(
                f"查询 {self.username} 加速券数量失败："
                "status 响应中缺少 data"
            )
            return None

        backpack = data.get("backpack")
        if not isinstance(backpack, dict):
            print(
                f"查询 {self.username} 加速券数量失败："
                "status 响应中缺少 backpack"
            )
            return None

        materials = backpack.get("materials")
        if not isinstance(materials, list):
            print(
                f"查询 {self.username} 加速券数量失败："
                "status 响应中缺少 backpack.materials"
            )
            return None

        for item in materials:
            if not isinstance(item, dict):
                continue
            if item.get("item_id") != "dungeon_accel_ticket":
                continue

            count = item.get("count")
            if isinstance(count, bool):
                return None

            try:
                count = int(count)
            except (TypeError, ValueError):
                print(
                    f"查询 {self.username} 加速券数量失败："
                    f"count={count!r}"
                )
                return None

            return max(0, count)

        # 背包里没有该 material，按 0 张处理。
        return 0

    def accelerate_battle(self) -> bool:
        """使用加速券立即完成当前战斗的等待。

        这不是跳过战斗，也不是无条件略过战斗结果：
        服务端会直接返回本次战斗的结算结果（winner / ticks），
        并把当前战斗状态置为 completed。

        API:
            POST /dungeon/node/battle/accelerate

        成功响应示例：
            {
                "code": 0,
                "data": {
                    "available_at": 1786999142,
                    "result": {
                        "ticks": 328,
                        "winner": "allies"
                    },
                    "status": "completed"
                }
            }

        accelerate 只把 battle_status 置为 completed，省掉战斗等待时间。
        当前节点本身此时仍可能是 completed=false，并保留 pending_loot /
        pending_member_status，因此 Runner 仍需要 GET node 读取结果，再调用
        battle/complete 正式结算当前战斗节点。
        """
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "battle_accelerate",
            error_message="快速完成战斗失败",
        )
        if response is None:
            return False

        result = self._response_json(
            response,
            context="快速完成战斗失败",
        )
        if result is None:
            return False

        data = result.get("data")
        if not isinstance(data, dict):
            print(f"快速完成战斗失败：响应中缺少 data：{result}")
            return False

        status = data.get("status")
        battle_result = data.get("result")
        if not isinstance(battle_result, dict):
            battle_result = {}

        winner = battle_result.get("winner")
        ticks = battle_result.get("ticks")

        if status != "completed":
            print(
                "快速完成战斗失败："
                f"服务器返回 status={status!r}"
            )
            return False

        print(
            "战斗已快速完成"
            f"（winner={winner!r}, ticks={ticks!r}）"
        )

        # completed 才代表 accelerate API 真正完成了节点。
        return True

    def complete_battle(self) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "battle_complete",
            error_message="完成战斗失败",
        )
        if response is None:
            return False

        print("战斗已完成")
        return True

    def enter_camp(self) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "camp_enter",
            error_message="进入营地失败",
        )
        if response is None:
            return False

        result = self._response_json(response, context="进入营地失败")
        if result is not None and "message" in result:
            print(result["message"])
        return True

    def leave_camp(self) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "camp_leave",
            error_message="离开营地失败",
        )
        if response is None:
            return False

        print("已离开营地")
        return True

    def choose_event(self, choice_index: int) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "event_choose",
            error_message="事件选项选择失败",
            json={"choice_index": choice_index},
        )
        return response is not None

    def open_treasure(self) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "treasure_open",
            error_message="开启宝箱失败",
        )
        if response is None:
            return False

        print("宝箱已开启")
        return True

    def get_shop(self, target_username: str) -> dict[str, Any] | None:
        if not self._require_dungeon():
            return None

        response = self._request(
            "GET",
            "shop_get",
            error_message=f"检查 {target_username} 的商店内容失败",
            params={"target_username": target_username},
        )
        if response is None:
            return None
        return self._response_json(response, context="查询商店失败")

    def buy_item(
        self,
        item_index: int,
        *,
        quantity: int = 1,
        target_username: str | None = None,
    ) -> bool:
        if not self._require_dungeon():
            return False

        payload: dict[str, Any] = {
            "item_index": item_index,
            "quantity": quantity,
        }
        if target_username is not None:
            payload["target_username"] = target_username

        response = self._request(
            "POST",
            "shop_buy",
            error_message="购买失败",
            json=payload,
        )
        if response is None:
            return False

        if target_username is None:
            print("已购买")
        else:
            print(f"已为 {target_username} 代购")
        return True

    def leave_shop(self) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "shop_leave",
            error_message="离开商店失败",
        )
        if response is None:
            return False

        print("已离开商店")
        return True

    def choose_branch(self, choice_index: int) -> bool:
        if not self._require_dungeon():
            return False

        response = self._request(
            "POST",
            "branch_choose",
            error_message="选择分支失败",
            json={"choice_index": choice_index},
        )
        if response is None:
            return False

        print(f"已选择分支 {choice_index}")
        return True

    def _require_dungeon(self) -> bool:
        if self.dungeon_id is not None:
            return True
        print("当前没有加入任何地下城")
        return False


# =========================
# ntfy 运行通知
# =========================


def _ntfy_setting(
    configured: str | None,
    env_name: str,
    default: str | None = None,
) -> str | None:
    """优先读取环境变量，其次读取运行设置；未配置则返回默认值。"""
    env_value = os.getenv(env_name)
    if env_value is not None:
        value = env_value.strip()
        return value or default

    if configured is None:
        return default

    value = str(configured).strip()
    return value or default


class NtfyNotifier:
    """给 Aether 运行过程发送独立 ntfy 推送。

    只要 NTFY_TOPIC / AETHER_NTFY_TOPIC 没配置，就完全禁用。
    推送使用 daemon thread，不阻塞地下城主流程。
    """

    def __init__(
        self,
        preset:DungeonPreset,
        settings:RuntimeSettings|None=None,
    ):
        settings=settings or load_runtime_settings()
        self.preset = preset
        self.topic = _ntfy_setting(
            settings.ntfy_topic,
            "AETHER_NTFY_TOPIC",
        )
        self.server = (
            _ntfy_setting(
                settings.ntfy_server,
                "AETHER_NTFY_SERVER",
                "https://ntfy.sh",
            )
            or "https://ntfy.sh"
        ).rstrip("/")
        self.token = _ntfy_setting(
            None,
            "AETHER_NTFY_TOKEN",
        )

    @property
    def enabled(self) -> bool:
        return bool(self.topic)

    def _publish_sync(
        self,
        message: str,
        *,
        priority: str,
        tags: str,
    ) -> None:
        if not self.topic:
            return

        topic = quote(self.topic, safe="")
        url = f"{self.server}/{topic}"

        # Title 故意只用 ASCII，避免 requests 对非 ASCII HTTP header
        # 的编码兼容问题；中文信息全部放在 body。
        headers = {
            "Title": "Aether",
            "Priority": priority,
            "Tags": tags,
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = requests.post(
                url,
                data=message.encode("utf-8"),
                headers=headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            print(f"ntfy 推送失败：{exc}")
            return

        if response.status_code >= 400:
            body = response.text[:300]
            print(
                f"ntfy 推送失败：HTTP {response.status_code}，"
                f"响应：{body}"
            )

    def publish(
        self,
        message: str,
        *,
        priority: str = "default",
        tags: str = "computer",
    ) -> None:
        """异步发送一条推送，不让通知网络延迟拖慢打本。"""
        from .notifications import allows
        if not allows("detail"):
            return
        if not self.enabled:
            return

        thread = threading.Thread(
            target=self._publish_sync,
            kwargs={
                "message": message,
                "priority": priority,
                "tags": tags,
            },
            name="aether-ntfy",
            daemon=True,
        )
        thread.start()

    def node_completed(
        self,
        *,
        node_index: Any,
        node_name: Any,
    ) -> None:
        if isinstance(node_index, int):
            display_index = node_index + 1
            prefix = f"节点 {display_index}"
        else:
            prefix = "当前节点"

        self.publish(
            f"{self.preset.label}\n"
            f"✓ {prefix}：{node_name} 已完成",
            priority="low",
            tags="heavy_check_mark",
        )

    def error(self, message: str) -> None:
        self.publish(
            f"{self.preset.label}\n"
            f"{message}",
            priority="high",
            tags="warning",
        )

    def paused(self, message: str) -> None:
        self.publish(
            f"{self.preset.label}\n"
            f"{message}",
            priority="default",
            tags="pause_button",
        )

    def completed(self) -> None:
        self.publish(
            f"{self.preset.label}\n"
            "地下城探索完毕",
            priority="default",
            tags="tada",
        )


# =========================
# 地下城布局统计
# =========================

_LAYOUT_STATS_FILE = pathlib.Path(cfg.AETHER_DATA_DIR) / "layout_stats.json"
_LAYOUT_STATS_LOCK = threading.Lock()


def _load_layout_stats_unlocked() -> dict[str, Any]:
    """读取 data/aether/layout_stats.json。

    文件不存在或损坏时返回空结构，不影响正常打本。
    """
    if not _LAYOUT_STATS_FILE.exists():
        return {
            "version": 1,
            "presets": {},
        }

    try:
        with _LAYOUT_STATS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        print(f"读取布局统计失败：{_LAYOUT_STATS_FILE}")
        return {
            "version": 1,
            "presets": {},
        }

    if not isinstance(data, dict):
        return {
            "version": 1,
            "presets": {},
        }

    presets = data.get("presets")
    if not isinstance(presets, dict):
        data["presets"] = {}

    data["version"] = 1
    return data


def _layout_composition_key(counts: dict[str, int]) -> str:
    """把节点数量压成稳定 key。

    例如：
        battle=2|branch=1|camp=1|elite=1|event=1|shop=1
    """
    return "|".join(
        f"{node_type}={count}"
        for node_type, count in sorted(counts.items())
        if count
    )


def _layout_sequence_key(layout: list[str] | tuple[str, ...]) -> str:
    """把 0:battle | 1:event ... 压成只保留节点顺序的 key。"""
    node_types: list[str] = []

    for entry in layout:
        text = str(entry)
        if ":" in text:
            _, node_type = text.split(":", 1)
        else:
            node_type = text
        node_types.append(node_type)

    return "|".join(node_types)


def record_layout_sample(
    preset: DungeonPreset,
    counts: dict[str, int],
    layout: list[str] | tuple[str, ...],
) -> dict[str, Any] | None:
    """记录一次 dungeon/search 产生的候选布局。

    统计维度：
      - total：该预设累计搜索次数
      - battle_counts：战斗节点数量直方图
      - compositions：节点数量组合
      - layouts：完整节点顺序

    返回本次更新后的简要统计，供控制台直接显示。
    """
    composition_key = _layout_composition_key(counts)
    sequence_key = _layout_sequence_key(layout)
    battle_count = int(counts.get("battle", 0))

    try:
        with _LAYOUT_STATS_LOCK:
            data = _load_layout_stats_unlocked()
            presets = data.setdefault("presets", {})

            record = presets.get(preset.key)
            if not isinstance(record, dict):
                record = {}
                presets[preset.key] = record

            record["name"] = preset.name
            record["preset_id"] = preset.preset_id
            record["difficulty"] = preset.difficulty

            total = int(record.get("total", 0)) + 1
            record["total"] = total

            battle_counts = record.get("battle_counts")
            if not isinstance(battle_counts, dict):
                battle_counts = {}
                record["battle_counts"] = battle_counts

            battle_key = str(battle_count)
            battle_counts[battle_key] = int(
                battle_counts.get(battle_key, 0)
            ) + 1

            compositions = record.get("compositions")
            if not isinstance(compositions, dict):
                compositions = {}
                record["compositions"] = compositions
            compositions[composition_key] = int(
                compositions.get(composition_key, 0)
            ) + 1

            layouts = record.get("layouts")
            if not isinstance(layouts, dict):
                layouts = {}
                record["layouts"] = layouts
            layouts[sequence_key] = int(
                layouts.get(sequence_key, 0)
            ) + 1

            record["updated_at"] = int(time.time())

            _LAYOUT_STATS_FILE.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temp_file = _LAYOUT_STATS_FILE.with_suffix(".json.tmp")
            with temp_file.open("w", encoding="utf-8") as file:
                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                file.write("\n")

            temp_file.replace(_LAYOUT_STATS_FILE)

            return {
                "total": total,
                "composition_count": compositions[composition_key],
                "battle_counts": dict(battle_counts),
            }

    except (OSError, TypeError, ValueError) as exc:
        print(f"保存布局统计失败：{exc}")
        return None


def print_layout_stats_summary(
    preset: DungeonPreset,
    counts: dict[str, int],
    layout: list[str] | tuple[str, ...],
) -> None:
    """记录一次布局，并打印当前经验概率。"""
    summary = record_layout_sample(preset, counts, layout)
    if summary is None:
        return

    total = int(summary["total"])
    composition_count = int(summary["composition_count"])
    battle_counts = summary["battle_counts"]

    composition_rate = (
        composition_count / total * 100
        if total
        else 0.0
    )

    battle_parts = []
    for key in sorted(
        battle_counts,
        key=lambda value: int(value)
        if str(value).isdigit()
        else 10**9,
    ):
        battle_parts.append(
            f"{key}战={battle_counts[key]}"
        )

    print(
        f"布局统计：{preset.key} 已记录 {total} 张\n"
        f"  本组合：{composition_count}/{total}"
        f"（{composition_rate:.2f}%）"
    )

    if battle_parts:
        print("  战斗数：" + "，".join(battle_parts))

    three_battle_count = int(battle_counts.get("3", 0))
    if three_battle_count or total >= 10:
        three_battle_rate = three_battle_count / total * 100
        print(
            f"  3战斗概率：{three_battle_count}/{total}"
            f"（{three_battle_rate:.2f}%）"
        )


# =========================
# 策略
# =========================


class DungeonStrategy:
    """只负责“遇到某种情况该怎么选”，不发送 HTTP 请求。"""

    def __init__(self,rules:StrategyRules|None=None):
        self.rules=rules or load_strategy_rules()

    def get_event_choice(
        self,event_id:str,event_overrides:dict[str,int]|None=None
    )->tuple[str,int]|None:
        event_id = str(event_id)

        configured = self.rules.event_choices.get(event_id)
        if configured is not None:
            choice_index=(event_overrides or {}).get(event_id,configured.choice_index)
            return configured.name,choice_index

        return None

    def get_branch_choice(self,preset_id: str) -> int | None:
        return self.rules.branch_choices.get(preset_id)

    def should_buy(self,item_name: str) -> bool:
        if any(marker in item_name for marker in self.rules.shop_buy_always_contains):
            return True

        if self.rules.shop_buy_three_star_marker in item_name:
            return not any(
                excluded in item_name
                for excluded in self.rules.shop_buy_three_star_excludes
            )

        return False

    def should_retreat_from_battle(self,battle_preset: str | None) -> bool:
        return battle_preset in self.rules.retreat_battle_presets


# =========================
# 地下城运行器
# =========================


class DungeonRunner:
    """负责把“当前节点 -> 处理 -> 下一节点”串起来。"""

    BATTLE_NODE_TYPES = {"battle", "elite", "boss"}
    TREASURE_NODE_TYPES = {"treasure", "boss_treasure"}

    def __init__(
        self,
        party: list[AetherClient],
        preset: DungeonPreset,
        strategy: DungeonStrategy | None = None,
        hooks: RuntimeHooks | None = None,
        fast_mode: bool = False,
        acceleration_mode: AccelerationMode | None = None,
        accel_min_wait_seconds: float | None = None,
        accel_ticket_reserve: int | None = None,
        skip_camp_wait: bool | None = None,
        resume:bool=False,
    ):
        if not party:
            raise ValueError("队伍不能为空")

        self.all_party=party
        self.clients_by_name={client.username:client for client in party}
        self.party=[
            self.clients_by_name[member.username]
            for member in preset.runtime_owned_members
        ]
        self.captain = self.clients_by_name.get(preset.leader.username)
        if self.captain is None:
            raise ValueError(f"缺少队长 Client：{preset.leader.username}")
        self.opener=self.clients_by_name.get(preset.opener.username)
        if self.opener is None:
            if not resume or not preset.opener.leave_after_enter:
                raise ValueError(f"缺少开本角色 Client：{preset.opener.username}")
            self.opener=self.captain
        self.preset = preset
        self.strategy = strategy or DungeonStrategy()
        self.hooks = hooks or RuntimeHooks()
        self.runtime_settings=load_runtime_settings()

        # fast_mode 继续作为旧单任务接口的兼容开关：
        #   /aether 快速 -> 战斗 always 加速 + 营地立即离开。
        #
        # 批量调度器会显式传 acceleration_mode，把“战斗是否烧票”
        # 和“营地是否等待”拆开。
        self.fast_mode = fast_mode

        if acceleration_mode is None:
            acceleration_mode = "always" if fast_mode else "never"
        if acceleration_mode not in {"never", "threshold", "always"}:
            raise ValueError(f"未知加速模式：{acceleration_mode!r}")
        self.acceleration_mode: AccelerationMode = acceleration_mode

        if accel_min_wait_seconds is None:
            accel_min_wait_seconds=float(
                self.runtime_settings.acceleration_balanced_min_wait_seconds
            )
        self.accel_min_wait_seconds = max(0.0, float(accel_min_wait_seconds))

        if accel_ticket_reserve is None:
            accel_ticket_reserve=self.runtime_settings.acceleration_ticket_reserve
        self.accel_ticket_reserve = max(0, int(accel_ticket_reserve))

        if skip_camp_wait is None:
            skip_camp_wait = fast_mode
        self.skip_camp_wait = bool(skip_camp_wait)

        self.notifier=NtfyNotifier(preset,self.runtime_settings)

        # 只有真正可能使用加速券时才读取库存。
        # 后续每成功使用一张就在内存里 -1，避免每场战斗都请求
        # 体积很大的 /status 响应。
        self._accel_ticket_counts: dict[str, int] | None = None

    def _prepare_runtime_party(self,dungeon_data:dict[str,Any])->bool:
        actual_leader=dungeon_data.get("leader_id")
        target_leader=self.preset.leader.username
        if actual_leader!=target_leader:
            if actual_leader!=self.preset.opener.username:
                print(f"当前队长异常：{actual_leader!r}")
                return False
            self.hooks.state(
                "transferring_leader",
                opener=self.preset.opener.username,
                captain=target_leader,
            )
            if not self.opener.transfer_dungeon_leader(target_leader):
                return False
            time.sleep(PARTY_ACTION_DELAY)

        members=dungeon_data.get("members")
        if not isinstance(members,list):
            print("地下城信息中缺少成员列表")
            return False
        present={
            member.get("key")
            for member in members
            if isinstance(member,dict) and isinstance(member.get("key"),str)
        }
        for member in self.preset.owned_members:
            if not member.leave_after_enter or member.username not in present:
                continue
            client=self.clients_by_name.get(member.username)
            if client is None:
                continue
            self.hooks.state("leaving_party",username=member.username)
            if not client.leave_dungeon():
                return False
            present.remove(member.username)
            time.sleep(PARTY_ACTION_DELAY)

        expected_members=set(self.preset.runtime_member_usernames)
        preset_members=set(self.preset.member_usernames)
        actual_status=None
        actual_leader=None
        actual_members:set[str]|None=None
        for attempt in range(PARTY_STATE_CHECK_ATTEMPTS):
            current=self.captain.get_current_dungeon(silent=True)
            data=current.get("data") if isinstance(current,dict) else None
            if isinstance(data,dict):
                actual_status=data.get("status")
                actual_leader=data.get("leader_id")
                current_members=data.get("members")
                if isinstance(current_members,list):
                    actual_members={
                        member.get("key")
                        for member in current_members
                        if isinstance(member,dict) and isinstance(member.get("key"),str)
                    }
                    if (
                        actual_status=="exploring"
                        and actual_leader==target_leader
                        and expected_members<=actual_members<=preset_members
                    ):
                        self.hooks.state(
                            "runtime_party_ready",
                            captain=target_leader,
                            dungeon_id=str(data.get("dungeon_id") or ""),
                        )
                        return True
            if attempt+1<PARTY_STATE_CHECK_ATTEMPTS:
                time.sleep(PARTY_ACTION_DELAY)
        print(
            "队长转移或成员退出后的队伍状态与预设不一致："
            f"状态={actual_status!r}，队长={actual_leader!r}，"
            f"成员={sorted(actual_members) if actual_members is not None else None!r}，"
            f"必须保留成员={sorted(expected_members)!r}，"
            f"预设成员={sorted(preset_members)!r}"
        )
        return False

    def run(self, *, resume: bool = False) -> bool:
        controller=self.captain if resume else self.opener
        dungeon = controller.get_current_dungeon()
        if dungeon is None:
            self.notifier.error("读取当前地下城失败，探索未开始")
            return False

        dungeon_data = dungeon.get("data")
        if not isinstance(dungeon_data, dict):
            print("当前地下城数据结构异常")
            self.notifier.error("当前地下城数据结构异常，探索停止")
            return False

        status = dungeon_data.get("status")

        if resume:
            if status != "exploring":
                print(f"无法恢复：当前地下城状态不是 exploring，而是 {status!r}")
                self.notifier.error(
                    f"无法恢复地下城：当前状态为 {status!r}"
                )
                return False
            print(
                f"恢复进行中的地下城："
                f"{self.strategy.rules.preset_names.get(self.preset.preset_id,self.preset.preset_id)} "
                f"· {self.preset.difficulty}"
            )
        else:
            self.hooks.state("entering",opener=self.preset.opener.username)
            if not self.opener.enter_dungeon():
                self.notifier.error(
                    self._append_error_detail(
                        "进入地下城失败",
                        self.opener.last_error,
                    )
                )
                return False
            dungeon=self.captain.get_current_dungeon()
            dungeon_data=dungeon.get("data") if isinstance(dungeon,dict) else None
            if not isinstance(dungeon_data,dict):
                self.notifier.error("进入后无法读取地下城，探索停止")
                return False

        if not self._prepare_runtime_party(dungeon_data):
            self.notifier.error(
                self._append_error_detail(
                    "准备运行队伍失败，探索停止",
                    get_latest_client_error(self.all_party),
                )
            )
            return False

        node = self.captain.get_current_node()
        if node is None:
            self.notifier.error("读取首个节点失败，探索停止")
            return False

        while True:
            # 停止请求只在“已经完整推进到一个新节点”时响应，
            # 不会把战斗/商店处理到一半直接杀掉。
            if self.hooks.stop_requested():
                print("收到停止请求，已在安全节点暂停")
                self.hooks.state("stopped")
                self.hooks.emit("Aether：已在安全节点暂停，地下城进度保留。")
                self.notifier.paused("已在安全节点暂停，地下城进度保留")
                return False

            # 兼容旧响应：如果当前节点响应里直接带 completion_reason，也视为结束。
            if "completion_reason" in node:
                print("地下城已完成")
                self.hooks.state("completed")
                self.notifier.completed()
                return True

            sanity = node.get("sanity")
            if isinstance(sanity, (int, float)) and sanity <= 1:
                print("san 值过低，强行撤离")
                self.captain.retreat_dungeon()
                self.notifier.error(
                    f"san 值过低（{sanity}），已强行撤离"
                )
                return False

            # 一个节点作为一个独立错误上下文。
            # 这样后面若失败，ntfy 只带本节点产生的新错误，不会串到旧请求。
            self._clear_party_errors()

            data = node.get("data")
            if isinstance(data, dict):
                node_type = data.get("node_type")
                node_name = NODE_NAMES.get(node_type, node_type)
                node_index = data.get("index")
            else:
                node_name = "未知节点"
                node_index = None

            if not self._handle_node(node):
                if isinstance(node_index, int):
                    display_index = node_index + 1
                    where = f"节点 {display_index}：{node_name}"
                else:
                    where = str(node_name)
                self.notifier.error(
                    self._append_error_detail(
                        f"{where} 处理失败，探索停止",
                        self._latest_client_error(),
                    )
                )
                return False

            next_result = self.captain.next_node()
            if next_result is None:
                if isinstance(node_index, int):
                    display_index = node_index + 1
                    where = f"节点 {display_index}：{node_name}"
                else:
                    where = str(node_name)
                self.notifier.error(
                    self._append_error_detail(
                        f"{where} 已处理，但推进下一节点失败",
                        self._latest_client_error(),
                    )
                )
                return False

            # 只有 /node/next 成功后才认为这个节点真正“推进完成”。
            self.notifier.node_completed(
                node_index=node_index,
                node_name=node_name,
            )

            # 当前前端协议：/node/next 顶层 settlement 表示进入结算。
            if next_result.get("settlement"):
                print("地下城已完成")
                self.notifier.completed()
                return True

            # 非结算状态下，重新 GET /dungeon/node 获取真正的下一节点详情。
            node = self.captain.get_current_node()
            if node is None:
                self.notifier.error(
                    self._append_error_detail(
                        "上一节点已推进，但读取下一节点失败，探索停止",
                        self._latest_client_error(),
                    )
                )
                return False

    def _handle_node(self, node: dict[str, Any]) -> bool:
        data = node.get("data")
        if not isinstance(data, dict):
            print(f"节点数据结构异常：{node}")
            return False

        node_type = data.get("node_type")
        node_name = NODE_NAMES.get(node_type, node_type)
        print(f"当前节点：{node_name}")
        self.hooks.state(
            "node",
            node_type=node_type,
            node_name=node_name,
            node_index=data.get("index"),
        )

        if node_type in self.BATTLE_NODE_TYPES:
            return self._handle_battle(data)
        if node_type == "camp":
            return self._handle_camp()
        if node_type == "event":
            return self._handle_event(data)
        if node_type in self.TREASURE_NODE_TYPES:
            return self.captain.open_treasure()
        if node_type == "shop":
            return self._handle_shop(data,node.get("sanity"))
        if node_type == "branch":
            return self._handle_branch()

        print(f"遇到未知节点类型：{node_type!r}，停止自动探索")
        return False

    def _clear_party_errors(self) -> None:
        for member in self.party:
            member.clear_last_error()

    def _latest_client_error(self) -> str | None:
        """返回当前节点处理中最近产生的底层客户端错误。"""
        return get_latest_client_error(self.party)

    @staticmethod
    def _append_error_detail(
        message: str,
        detail: str | None,
    ) -> str:
        return append_error_detail(message, detail)

    def _load_accel_ticket_counts(self) -> dict[str, int]:
        """第一次快速战斗时读取整队加速券库存。

        单个账号查询失败时把它视为 0，避免因为一个 status 请求异常
        就完全阻断另外两个账号的加速券使用。
        """
        counts: dict[str, int] = {}

        for member in self.party:
            count = member.get_accel_ticket_count()
            if count is None:
                print(
                    f"{member.username} 加速券数量读取失败，"
                    "本次运行暂按 0 张处理"
                )
                count = 0

            counts[member.username] = count

        self._accel_ticket_counts = counts

        inventory = "，".join(
            f"{member.username}={counts[member.username]}"
            for member in self.party
        )
        print(f"加速券库存：{inventory}")

        return counts

    def _choose_accelerator(self) -> tuple[AetherClient, int] | None:
        """选择“超过库存保护线”且加速券最多的受控角色。

        注意：
        DungeonRunner.party 来自 select_party()，只包含 owned Client。
        offline friend 没有 Client，因此不会进入候选，也绝不可能发送
        battle/accelerate 请求或消耗加速券。

        例如保护线为 300：
        - 301 张可以使用 1 张；
        - 300 张不能再使用；
        因此正常情况下不会把库存烧到保护线以下。

        数量并列时，max() 保留 party 中最先出现的成员。
        """
        counts = self._accel_ticket_counts
        if counts is None:
            counts = self._load_accel_ticket_counts()

        candidates = [
            member
            for member in self.party
            if counts.get(member.username, 0) > self.accel_ticket_reserve
        ]
        if not candidates:
            return None

        member = max(
            candidates,
            key=lambda client: counts.get(client.username, 0),
        )
        return member, counts[member.username]

    def _mark_accel_ticket_used(self, username: str) -> None:
        """服务器确认 accelerate 成功后再扣本地缓存。"""
        counts = self._accel_ticket_counts
        if counts is None:
            return

        counts[username] = max(0, counts.get(username, 0) - 1)

    def _handle_battle(self, node_data: dict[str, Any]) -> bool:
        resumed=self._resume_finished_battle(node_data)
        if resumed is not None:
            return resumed
        battle_preset = node_data.get("battle_preset")

        # 保留旧普通模式的指定战斗撤退策略。
        # /aether 快速 仍按旧行为不走该撤退分支；
        # 批量任务默认 skip_camp_wait=True，因此同样以“完成整把”为优先。
        if (
            not self.fast_mode
            and self.strategy.should_retreat_from_battle(battle_preset)
        ):
            print(f"遇到需要撤退的战斗：{battle_preset}")
            self.captain.retreat_dungeon()
            return False

        # 必须先 start，才能从 available_at 得知这一场实际要等多久。
        battle = self.captain.start_battle()
        if battle is None:
            error=self.captain.last_error or ""
            if "HTTP 400" in error and "战斗已经执行完毕" in error:
                current=self.captain.get_current_node()
                data=current.get("data") if isinstance(current,dict) else None
                if (
                    isinstance(data,dict)
                    and isinstance(node_data.get("index"),int)
                    and data.get("index")==node_data["index"]
                    and data.get("node_type")==node_data.get("node_type")
                ):
                    resumed=self._resume_finished_battle(data)
                    if resumed is True:
                        self.captain.clear_last_error()
                    if resumed is not None:
                        return resumed
            return False

        if battle.forced_exit:
            dungeon = self.captain.get_current_dungeon()
            if dungeon is None:
                return False

            status = dungeon.get("data", {}).get("status")
            if status == "exploring":
                print("forced_exit 后地下城仍处于 exploring，继续探索")
                return True

            if status in {"completed", "failed"}:
                print(f"forced_exit 后地下城状态：{status}")
                return status == "completed"

            print(f"forced_exit 后地下城状态未知：{status!r}")
            return False

        should_accelerate = False
        reason = ""

        if self.acceleration_mode == "always":
            should_accelerate = True
            reason = "策略要求始终加速"

        elif self.acceleration_mode == "threshold":
            if battle.wait_time >= self.accel_min_wait_seconds:
                should_accelerate = True
                reason = (
                    f"预计等待 {int(battle.wait_time)} 秒 "
                    f">= 阈值 {int(self.accel_min_wait_seconds)} 秒"
                )
            else:
                reason = (
                    f"预计等待 {int(battle.wait_time)} 秒 "
                    f"< 阈值 {int(self.accel_min_wait_seconds)} 秒"
                )

        else:
            reason = "当前任务禁止使用加速券"

        accelerator: AetherClient | None = None
        accelerator_before = 0

        if should_accelerate:
            selected = self._choose_accelerator()

            if selected is None:
                print(
                    f"本场原计划使用加速券（{reason}），"
                    f"但所有受控角色都已到库存保护线 "
                    f"{self.accel_ticket_reserve} 张或以下，改为普通等待"
                )
                self.hooks.state(
                    "battle",
                    acceleration_mode=self.acceleration_mode,
                    acceleration_skipped="reserve",
                    wait_seconds=battle.wait_time,
                )
            else:
                accelerator, accelerator_before = selected
                self.hooks.state(
                    "battle_accelerating",
                    accelerator=accelerator.username,
                    tickets=accelerator_before,
                    reserve=self.accel_ticket_reserve,
                    acceleration_mode=self.acceleration_mode,
                    wait_seconds=battle.wait_time,
                )
                print(
                    f"加速：{reason}；由 {accelerator.username} 使用加速券"
                    f"（当前 {accelerator_before} 张，"
                    f"保护线 {self.accel_ticket_reserve}）"
                )
        else:
            print(f"不加速：{reason}")
            self.hooks.state(
                "battle",
                acceleration_mode=self.acceleration_mode,
                wait_seconds=battle.wait_time,
            )

        if accelerator is not None:
            # 加速接口无 payload，消耗的是发送这个请求的角色自己的券。
            if not accelerator.accelerate_battle():
                return False

            # 只有服务器确认 accelerate 成功后才修改本地缓存。
            self._mark_accel_ticket_used(accelerator.username)
            remaining = (
                self._accel_ticket_counts.get(accelerator.username, 0)
                if self._accel_ticket_counts is not None
                else 0
            )
            print(
                f"{accelerator.username} 加速券剩余（本地缓存）："
                f"{remaining}"
            )

            result = self.captain.get_current_node()
            if result is None:
                return False

            self._print_battle_result(result)
            return self.captain.complete_battle()

        # 不加速，正常等待服务器 available_at。
        time.sleep(max(0.0, battle.wait_time + BATTLE_FINISH_BUFFER))

        result = self.captain.get_current_node()
        if result is None:
            return False

        self._print_battle_result(result)
        return self.captain.complete_battle()

    def _resume_finished_battle(self,node_data:dict[str,Any])->bool|None:
        """恢复已结束的战斗，只在节点结算成功后允许推进。"""
        if node_data.get("completed") is True:
            print("当前战斗节点已结算，继续推进")
            return True
        battle_status=node_data.get("battle_status")
        if isinstance(battle_status,dict):
            battle_status=battle_status.get("status")
        if battle_status=="completed":
            print("当前战斗已执行完毕，补办节点结算")
            return self.captain.complete_battle()
        return None

    @staticmethod
    def _print_battle_result(node: dict[str, Any]) -> None:
        data = node.get("data", {})
        battle_result = data.get("battle_result", {})
        winner = battle_result.get("winner")

        if winner is None:
            print("战斗结果：服务器响应中暂无 battle_result")
            return

        print("战斗结果：")
        print(f"  {'胜利' if winner == 'allies' else '失败'}")

        if winner == "allies":
            loot = data.get("loot_earned", {})
            print(
                f"  获得奖励：{loot.get('exp', '?')} 经验，"
                f"{loot.get('money', '?')} 金币"
            )

    def _handle_camp(self) -> bool:
        if not self.captain.enter_camp():
            return False

        if self.skip_camp_wait:
            print("批量/快速节点模式：已进入营地，跳过停留等待并立即离开")
            self.hooks.state("camp_accelerated")
            return self.captain.leave_camp()

        print(f"营地停留 {self.runtime_settings.camp_stay_time} 秒")
        time.sleep(self.runtime_settings.camp_stay_time)

        return self.captain.leave_camp()

    def _handle_event(self, node_data: dict[str, Any]) -> bool:
        event = node_data.get("event")
        if not isinstance(event, dict):
            print(f"事件数据结构异常：{node_data}")
            return False

        event_id = event.get("id")
        event_name = event.get("name", event_id)

        raw_options = event.get("choices")
        if not isinstance(raw_options, list):
            raw_options = event.get("options")
        if not isinstance(raw_options, list):
            raw_options = []

        # 无分支事件在 API 中没有真正的 choices/options：
        #
        #   "type": "plain",
        #   "options": []
        #
        # 前端表现上相当于只有一个“继续/确认”按钮。旧逻辑会把它当作
        # “未知事件但没有任何选项”，批量模式因为没有 QQ 交互处理器而直接失败。
        #
        # random 等类型也可能返回空 options；只有一个选项的普通事件同样
        # 没有决策空间。只要选项不超过一个，就固定向 event/choice 提交
        # choice_index=0，不写入全局事件配置。
        if len(raw_options)<=1:
            print(f"遇到无分支事件：{event_name}，自动继续")
            self.hooks.state(
                "event_plain",
                event_id=str(event_id or ""),
                event_name=str(event_name or event_id or "未知事件"),
            )

            if not self.captain.choose_event(0):
                return False

            self.hooks.state("event_resolved")
            return True

        choice = self.strategy.get_event_choice(event_id,self.preset.event_overrides)
        learned_event: UnknownEvent | None = None

        if choice is None:
            option_names: list[str] = []
            for index, option in enumerate(raw_options):
                if isinstance(option, dict):
                    label = (
                        option.get("name")
                        or option.get("text")
                        or option.get("label")
                        or option.get("description")
                    )
                    option_names.append(str(label or f"选项 {index}"))
                else:
                    option_names.append(str(option))

            unknown = UnknownEvent(
                event_id=str(event_id or ""),
                event_name=str(event_name or event_id or "未知事件"),
                options=tuple(option_names),
                raw=event,
            )
            learned_event = unknown

            print(f"遇到未知事件：{unknown.event_name}")
            print(f"事件信息：{json.dumps(event, ensure_ascii=False, indent=2)}")

            self.hooks.state(
                "waiting_event",
                event_id=unknown.event_id,
                event_name=unknown.event_name,
                options=list(unknown.options),
            )

            if self.hooks.choose_unknown_event is None:
                self.hooks.emit(
                    f"Aether：遇到未知事件「{unknown.event_name}」，"
                    "当前没有交互处理器，已暂停。"
                )
                return False

            choice_index = self.hooks.choose_unknown_event(unknown)
            if choice_index is None:
                print("未知事件未选择，停止自动探索")
                return False

            choice_name = (
                unknown.options[choice_index]
                if 0 <= choice_index < len(unknown.options)
                else f"选项 {choice_index}"
            )
        else:
            choice_name, choice_index = choice

        print(f"遇到事件：{event_name}")
        if not self.captain.choose_event(choice_index):
            return False

        print(f"已选择事件选项：{choice_name}")

        # 只有服务器确认选择成功后，才把未知事件写入全局策略。
        if learned_event is not None:
            try:
                saved=save_event_choice(
                    learned_event.event_id,learned_event.event_name,choice_index
                )
                self.strategy.rules.event_choices[learned_event.event_id]=saved
                print(
                    f"已保存全局事件选择："
                    f"{learned_event.event_id} -> {choice_index}"
                )
                self.hooks.emit(
                    f"Aether：已将「{learned_event.event_name}」"
                    f"选择 {choice_index}，以后将自动处理。"
                )
            except (AetherConfigError,OSError) as exc:
                print(f"保存全局事件选择失败：{exc}")
                self.hooks.emit(
                    f"Aether：事件已处理，但「{learned_event.event_name}」"
                    "的选择未能写入全局策略配置。"
                )

        self.hooks.state("event_resolved")
        return True

    def _handle_shop(self,node_data:dict[str,Any],current_sanity:Any)->bool:
        player_shops = node_data.get("player_shops")
        if not isinstance(player_shops, dict):
            print("商店数据中缺少 player_shops")
            return False

        rules=load_shop_rules()
        shops=[]

        # DungeonRunner.party 只包含 owned Client；offline friend 没有 Client，
        # 因此不会查询商店、也不会尝试购买物品。
        #
        # 队长与最终站位在 v18 后已经分离，不能再假设 self.party[0]
        # 一定是 captain。先处理 captain，再遍历所有“其他 owned Client”。
        own_items=node_data.get("shop_items")
        if not isinstance(own_items,list):
            print(f"商店物品列表异常：{own_items!r}")
            return False
        shops.append((self.captain.username,own_items,node_data.get("current_money"),None))

        for member in self.party:
            if member.username == self.captain.username:
                continue

            shop = self.captain.get_shop(member.username)
            if shop is None:
                return False

            data=shop.get("data")
            if not isinstance(data,dict) or not isinstance(data.get("shop_items"),list):
                print(f"{member.username} 的商店数据异常：{shop!r}")
                return False
            shops.append((member.username,data["shop_items"],data.get("current_money"),member.username))

        sanity_slots:dict[str,set[int]]={}
        offers=[]
        balances={}
        for username,items,money,_target_username in shops:
            balances[username]=money if isinstance(money,int) and not isinstance(money,bool) else 0
            for item_index,item in enumerate(items):
                if not is_sanity_item(item):
                    continue
                sanity_slots.setdefault(username,set()).add(item_index)
                recovery=sanity_recovery(item)
                if recovery is None:
                    print(f"无法解析理智商品恢复量，已跳过：{item!r}")
                    continue
                price=item.get("price") if isinstance(item,dict) else None
                remaining=item.get("remaining") if isinstance(item,dict) else None
                if (
                    not isinstance(price,int)
                    or isinstance(price,bool)
                    or not isinstance(remaining,int)
                    or isinstance(remaining,bool)
                ):
                    print(f"理智商品数据异常，已跳过：{item!r}")
                    continue
                offers.append(SanityOffer(
                    username=username,
                    item_index=item_index,
                    recovery=recovery,
                    price=max(0,price),
                    remaining=max(0,remaining),
                ))

        if isinstance(current_sanity,(int,float)) and not isinstance(current_sanity,bool):
            purchases=select_sanity_purchases(int(current_sanity),rules.sanity,offers,balances)
            if purchases:
                total=sum(purchase.recovery for purchase in purchases)
                print(f"当前理智 {int(current_sanity)}，计划购买恢复 {total} 点理智")
            for purchase in purchases:
                target_username=None if purchase.username==self.captain.username else purchase.username
                if not self.captain.buy_item(
                    purchase.item_index,
                    quantity=purchase.quantity,
                    target_username=target_username,
                ):
                    return False
        elif rules.sanity.buyers:
            print("商店节点缺少当前理智，已跳过理智购买")

        for username,items,_money,target_username in shops:
            if not self._maybe_buy_shop_items(
                items,
                username=username,
                rules=rules,
                target_username=target_username,
                skipped_indexes=sanity_slots.get(username,set()),
            ):
                return False

        return self.captain.leave_shop()

    def _maybe_buy_shop_items(
        self,
        items: Any,
        *,
        username:str,
        rules:ShopRules,
        target_username: str | None = None,
        skipped_indexes:set[int]|None=None,
    ) -> bool:
        if not isinstance(items,list):
            print(f"商店物品列表异常：{items!r}")
            return False
        for item_index,item in enumerate(items[:3]):
            if not isinstance(item,dict):
                print(f"商店物品数据异常：{item!r}")
                return False
            if skipped_indexes and item_index in skipped_indexes:
                continue
            rule=effective_rule(rules,username,item_index+1)
            if rule=="never":
                continue
            if rule=="legacy" and not self.strategy.should_buy(str(item.get("name",""))):
                continue
            if not self.captain.buy_item(item_index,target_username=target_username):
                return False
        return True

    def _handle_branch(self) -> bool:
        choice_index = self.strategy.get_branch_choice(self.preset.preset_id)
        if choice_index is None:
            print(f"副本 {self.preset.preset_id} 没有配置分支选择，停止自动探索")
            return False
        if not self.captain.choose_branch(choice_index):
            return False

        # 分支确认后服务器才生成后续节点，立即刷新完整地下城状态，
        # 让 checkpoint 和 Web 都能显示新生成的路线。
        current=self.captain.get_current_dungeon(silent=True)
        data=current.get("data") if isinstance(current,dict) else None
        if isinstance(data,dict) and isinstance(data.get("nodes"),list):
            self.hooks.state("branch_resolved",nodes=data["nodes"])
        else:
            print("分支已选择，但读取新节点列表失败")
        return True


# =========================
# 组队与任务调度
# =========================


def load_oauth_token() -> str | None:
    """读取共享的水鱼 OAuth token。

    优先级：
    1. 环境变量 AETHER_OAUTH_TOKEN
    2. data/aether/oauth_token.txt

    oauth_token.txt 只放 token 本体，不要加引号。
    """
    env_token = os.getenv("AETHER_OAUTH_TOKEN")
    if env_token:
        token = env_token.strip()
        if token:
            return token

    token_file = pathlib.Path(cfg.AETHER_DATA_DIR) / "oauth_token.txt"
    if token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(f"读取 OAuth token 文件失败：{exc}")
        else:
            if token:
                return token

    return None


def discover_oauth_characters(token: str) -> tuple[str, ...]:
    """从 /account 自动发现当前水鱼账号下的所有 Aether 角色。

    会取运行设置中的第一个回退角色作为探针，
    同时带 query + X-Aether-Character。
    即便以后新增小号，也会从响应 characters 中自动发现。
    """
    token = str(token).strip()
    if not token:
        return ()

    session = requests.Session()
    session.cookies.set(
        AETHER_AUTH_COOKIE_NAME,
        token,
        domain="chiyuki.diving-fish.com",
        path="/",
    )

    configured=load_runtime_settings().account_usernames
    seed = None
    if isinstance(configured, (list, tuple)) and configured:
        seed = str(configured[0])

    kwargs: dict[str, Any] = {"timeout": REQUEST_TIMEOUT}
    if seed:
        kwargs["params"] = {AETHER_CHARACTER_PARAM: seed}
        kwargs["headers"] = {AETHER_CHARACTER_HEADER: seed}

    try:
        response = session.get(
            BASE_URL + API_ENDPOINTS["account"],
            **kwargs,
        )
    except requests.RequestException as exc:
        print(f"自动发现 Aether 角色失败：网络异常：{exc}")
        return ()

    if not response.ok:
        print(
            "自动发现 Aether 角色失败："
            f"HTTP {response.status_code}: {response.text[:500]}"
        )
        return ()

    try:
        result = response.json()
    except ValueError:
        print("自动发现 Aether 角色失败：/account 返回非 JSON")
        return ()

    data = result.get("data") if isinstance(result, dict) else None
    characters = data.get("characters") if isinstance(data, dict) else None
    if not isinstance(characters, list):
        print("自动发现 Aether 角色失败：响应缺少 data.characters")
        return ()

    usernames: list[str] = []
    seen: set[str] = set()

    for item in characters:
        if not isinstance(item, dict):
            continue
        username = item.get("username")
        if not isinstance(username, str) or not username or username in seen:
            continue
        seen.add(username)
        usernames.append(username)

    return tuple(usernames)


def load_accounts() -> list[Account]:
    """读取当前可控制的 Aether 角色。

    OAuth 模式优先从 /account 自动发现全部角色；
    如果自动发现失败，则回退到 settings.json 的 account_usernames。
    """
    oauth_token = load_oauth_token()
    if oauth_token:
        usernames = discover_oauth_characters(oauth_token)
        if usernames:
            print(
                "OAuth 自动发现角色："
                + "，".join(usernames)
            )
            return [Account(username=username) for username in usernames]

    configured=load_runtime_settings().account_usernames

    password = os.getenv("AETHER_PASSWORD")
    return [
        Account(username=str(username), password=password)
        for username in configured
    ]


def initialize_client_pool() -> dict[str, AetherClient] | None:
    """初始化一次 OAuth 客户端池，供批量调度器长期复用。"""
    accounts = load_accounts()
    clients = login_all_accounts(
        accounts,
        allow_password_prompt=False,
        password_provider=None,
    )
    if clients is None:
        return None
    return {client.username: client for client in clients}


def login_all_accounts(
    accounts: list[Account],
    *,
    allow_password_prompt: bool = True,
    password_provider: Callable[[str], str | None] | None = None,
) -> list[AetherClient] | None:
    """登录并创建全部 Aether 角色客户端。

    新流程优先：
        一个水鱼 OAuth token
        -> 多个 AetherClient
        -> 每个请求自动带 ?_aether_character=<角色>

    兼容旧流程：
        如果没有配置 AETHER_OAUTH_TOKEN，
        仍尝试旧 per-character Cookie / password 登录。
    """
    oauth_token = load_oauth_token()

    if oauth_token:
        clients: list[AetherClient] = []
        print(
            "检测到水鱼 OAuth 登录态，"
            f"准备加载 {len(accounts)} 个 Aether 角色"
        )

        for account in accounts:
            client = AetherClient(account)

            if not client.try_oauth_login(oauth_token):
                detail = client.last_error or "未知 OAuth 验证错误"
                print(
                    f"{account.username} OAuth 角色验证失败："
                    f"{detail}"
                )
                return None

            clients.append(client)

        print(
            "OAuth 多角色初始化完成："
            + "，".join(client.username for client in clients)
        )
        return clients

    # -------------------------
    # 兼容旧认证流程
    # -------------------------
    print(
        "未配置 AETHER_OAUTH_TOKEN，"
        "尝试旧 Cookie / 密码登录兼容流程"
    )

    clients: list[AetherClient] = []

    shared_password = next(
        (account.password for account in accounts if account.password),
        None,
    )

    for account in accounts:
        client = AetherClient(account)

        if client.try_cookie_login():
            clients.append(client)
            continue

        if not shared_password:
            if password_provider is not None:
                shared_password = password_provider(account.username)

                if not shared_password:
                    print(
                        f"{account.username} Cookie 已失效，"
                        "QQ 侧未提供密码，停止登录"
                    )
                    return None

            elif allow_password_prompt:
                shared_password = getpass.getpass(
                    "检测到 Cookie 失效，请输入 Aether 密码（不会显示）："
                )

            else:
                print(
                    f"{account.username} Cookie 已失效，"
                    "且当前没有可用的密码输入通道"
                )
                return None

        if not client.login_with_password(shared_password):
            print(f"{account.username} 登录失败，停止执行")
            return None

        clients.append(client)

    return clients


def get_latest_client_error(
    clients: list[AetherClient],
) -> str | None:
    """返回一组客户端中最近发生的底层错误。"""
    failed = [
        client
        for client in clients
        if client.last_error
    ]
    if not failed:
        return None

    client = max(
        failed,
        key=lambda item: item.last_error_at,
    )
    return f"{client.username}: {client.last_error}"


def append_error_detail(
    message: str,
    detail: str | None,
) -> str:
    """给面向用户的错误消息追加底层 HTTP / JSON 详情。"""
    if not detail:
        return message
    return f"{message}\n错误详情：{detail}"


def create_party(
    party: list[AetherClient],
    preset: DungeonPreset,
    hooks: RuntimeHooks | None = None,
    layout_rules:dict[str,LayoutRule]|None=None,
) -> bool:
    """创建队伍。

    owned:
        切换自己的角色预设，并通过 /dungeon/join 加入。

    friend:
        由队长通过 /dungeon/recruit 以 offline_friend 招募。
        离线好友没有 Client，也不参与并发资源锁。
    """
    if not party:
        print("队伍不能为空")
        return False

    clients_by_name = {client.username: client for client in party}

    opener=clients_by_name.get(preset.opener.username)
    if opener is None:
        print(f"缺少开本角色 Client：{preset.opener.username}")
        return False

    # 所有受控角色先切好自己的预设。
    for member in preset.owned_members:
        client = clients_by_name.get(member.username)
        if client is None:
            print(f"缺少自有角色 Client：{member.username}")
            return False

        preset_index = member.preset_index
        if preset_index is None or not 0 <= preset_index <= 4:
            print(
                f"{member.username} 的预设槽位无效：{preset_index}"
            )
            return False

        if not client.apply_preset(preset_index):
            print(f"{member.username} 切换预设失败，停止创建队伍")
            return False

        time.sleep(PARTY_ACTION_DELAY)

    if not search_acceptable_dungeon(opener,preset,hooks,layout_rules=layout_rules):
        print("没有取得可接受的地下城布局，无法继续后续操作")
        return False

    if opener.dungeon_id is None:
        print("筛图结束但没有取得 dungeon_id，停止执行")
        return False

    # party 表示进入时站位；实际队长和开本角色都可以不在第 1 位。
    # 按 party 声明顺序加入/招募，但跳过已经创建地下城的开本角色。
    for member in preset.party:
        if member.username == preset.opener.username:
            continue

        time.sleep(PARTY_ACTION_DELAY)

        if member.controlled:
            client = clients_by_name.get(member.username)
            if client is None:
                print(f"缺少自有角色 Client：{member.username}")
                return False

            if not client.join_dungeon(opener.dungeon_id):
                print(f"{member.username} 未能成功加入队伍")
                return False
        else:
            if not opener.recruit_offline_friend(member.username):
                return False

    time.sleep(PARTY_ACTION_DELAY)
    return reorder_party(opener,preset.member_usernames)


def reorder_party(captain: AetherClient, party_order: tuple[str, ...]) -> bool:
    """把服务器中的队伍排列成任务里声明的用户名顺序。"""
    for target_index, username in enumerate(party_order):
        dungeon = captain.get_current_dungeon()
        if dungeon is None:
            return False

        members = dungeon.get("data", {}).get("members")
        if not isinstance(members, list):
            print("地下城信息中缺少成员列表")
            return False

        from_index = next(
            (
                index
                for index, member in enumerate(members)
                if isinstance(member, dict) and member.get("key") == username
            ),
            None,
        )
        if from_index is None:
            print(f"队伍中没有找到成员：{username}")
            return False

        if from_index != target_index:
            if not captain.reorder_members(from_index, target_index):
                return False

    return True




def get_search_nodes(client: AetherClient) -> list[dict[str, Any]]:
    """读取最近一次 /dungeon/search 响应中的 nodes。"""
    result = client.last_search_result
    if not isinstance(result, dict):
        return []

    data = result.get("data")
    if not isinstance(data, dict):
        return []

    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        return []

    return [node for node in nodes if isinstance(node, dict)]


def summarize_search_layout(client: AetherClient) -> list[str]:
    """把 search 阶段已经生成的节点类型压缩成可读列表。"""
    summary: list[str] = []

    for node in get_search_nodes(client):
        index = node.get("index", "?")
        node_type = str(node.get("node_type", "unknown"))
        summary.append(f"{index}:{node_type}")

    return summary


def normalize_runtime_nodes(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    result = []
    for position, node in enumerate(value):
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("node_type", ""))
        if node_type not in NODE_NAMES:
            continue
        index = node.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            index = position
        result.append({"index": index, "node_type": node_type})
    return tuple(result)


def summarize_runtime_nodes(client: AetherClient) -> list[dict[str, Any]]:
    return list(normalize_runtime_nodes(get_search_nodes(client)))


def count_search_layout(client: AetherClient) -> dict[str, int]:
    """统计 search 返回的各类节点数量。"""
    counts: dict[str, int] = {}

    for node in get_search_nodes(client):
        node_type = str(node.get("node_type", "unknown"))
        counts[node_type] = counts.get(node_type, 0) + 1

    return counts


def score_search_layout(
    client: AetherClient,
    rule: LayoutRule,
) -> tuple[float, dict[str, int]]:
    """按当前副本的 LayoutRule 计算节点布局分数。"""
    counts = count_search_layout(client)
    score = sum(
        count * rule.node_weights.get(node_type, 0)
        for node_type, count in counts.items()
    )
    return score, counts


def _format_layout_counts(counts: dict[str, int]) -> str:
    preferred_order = (
        "battle",
        "elite",
        "boss",
        "shop",
        "event",
        "camp",
        "treasure",
        "boss_treasure",
        "branch",
    )

    parts: list[str] = []
    used: set[str] = set()

    for node_type in preferred_order:
        count = counts.get(node_type, 0)
        if count:
            parts.append(f"{NODE_NAMES.get(node_type, node_type)}={count}")
            used.add(node_type)

    for node_type, count in counts.items():
        if node_type not in used:
            parts.append(f"{NODE_NAMES.get(node_type, node_type)}={count}")

    return "，".join(parts)


def search_acceptable_dungeon(
    captain: AetherClient,
    preset: DungeonPreset,
    hooks: RuntimeHooks | None = None,
    *,
    layout_rules:dict[str,LayoutRule]|None=None,
) -> bool:
    """搜索地下城，并判断是否接受当前节点布局。

    两种模式：

    1. 人工筛图：rule.min_score is None
       search -> 显示节点统计与评分 -> 等待输入
         y: 接受
         n: disband 后刷新
         q: disband 后终止任务

       人工模式不受 max_attempts 限制。

    2. 自动筛图：rule.min_score 为数值
       search -> 评分
         达标: 接受
         未达标: disband 后重搜
       最多尝试 rule.max_attempts 次。
    """
    hooks = hooks or RuntimeHooks()
    rule_name = preset.layout_rule or preset.preset_id
    rule=(layout_rules or DUNGEON_LAYOUT_RULES).get(rule_name)

    # 没有配置规则时保持普通搜索行为。
    if rule is None:
        searched = captain.search_dungeon(
            preset.difficulty,
            preset.preset_id,
            preset.visibility,
            preset.label,
        )
        if searched:
            hooks.state(
                "layout_accepted",
                nodes=summarize_runtime_nodes(captain),
            )
        return searched

    attempt = 0

    while True:
        attempt += 1

        if not captain.search_dungeon(
            preset.difficulty,
            preset.preset_id,
            preset.visibility,
            preset.label,
        ):
            return False

        if captain.dungeon_id is None:
            print("搜索成功但没有取得 dungeon_id")
            return False

        score, counts = score_search_layout(captain, rule)
        layout = summarize_search_layout(captain)
        runtime_nodes = summarize_runtime_nodes(captain)

        # 每一张候选图都作为独立样本记录；无论最终接受还是刷新。
        # 这正好对应实际 reroll 的生成概率。
        print_layout_stats_summary(
            preset,
            counts,
            layout,
        )

        if rule.min_score is None:
            print(f"布局候选 #{attempt}：{_format_layout_counts(counts)}")
        else:
            max_attempts = max(1, rule.max_attempts)
            print(
                f"布局候选 {attempt}/{max_attempts}："
                f"{_format_layout_counts(counts)}"
            )

        print(f"  评分：{score:g}")
        if layout:
            print("  节点：" + " | ".join(layout))

        # -------------------------
        # 人工筛图模式
        # -------------------------
        if rule.min_score is None:
            candidate = LayoutCandidate(
                attempt=attempt,
                score=score,
                counts=dict(counts),
                layout=tuple(layout),
            )
            hooks.state(
                "waiting_layout",
                attempt=attempt,
                score=score,
                counts=dict(counts),
                layout=list(layout),
                nodes=runtime_nodes,
            )

            if hooks.choose_layout is None:
                # 非交互调用时保持保守：接受第一张，不死等 stdin。
                decision = "accept"
            else:
                decision = hooks.choose_layout(candidate)

            if decision == "accept":
                print("接受当前布局")
                hooks.state(
                    "layout_accepted",
                    score=score,
                    nodes=runtime_nodes,
                )
                return True

            if decision == "abort":
                print("放弃当前地下城")
                captain.disband_dungeon()
                return False

            if decision == "refresh":
                print("解散当前地下城并刷新下一张...")
                if not captain.disband_dungeon():
                    return False
                print(f"洗牌冷却 {DUNGEON_REROLL_DELAY:g} 秒")
                time.sleep(DUNGEON_REROLL_DELAY)
                continue

            print(f"未知布局决策：{decision!r}")
            return False

        # -------------------------
        # 自动筛图模式
        # -------------------------
        if score >= rule.min_score:
            print(
                f"  达到最低接受分 {rule.min_score:g}，"
                "接受当前布局"
            )
            hooks.state(
                "layout_accepted",
                score=score,
                nodes=runtime_nodes,
            )
            return True

        print(f"  低于最低接受分 {rule.min_score:g}")

        max_attempts = max(1, rule.max_attempts)
        if attempt >= max_attempts:
            if rule.accept_last_on_exhausted:
                print("  已达到最大刷新次数，接受最后一张布局")
                hooks.state(
                    "layout_accepted",
                    score=score,
                    nodes=runtime_nodes,
                )
                return True

            print("  已达到最大刷新次数，放弃当前任务")
            captain.disband_dungeon()
            return False

        print("  解散当前地下城并重新搜索...")
        if not captain.disband_dungeon():
            return False

        print(f"  洗牌冷却 {DUNGEON_REROLL_DELAY:g} 秒")
        time.sleep(DUNGEON_REROLL_DELAY)

def select_party(
    clients: list[AetherClient],
    party_config: tuple[PartyMember, ...],
) -> list[AetherClient] | None:
    """按预设顺序选择所有受控角色 Client；离线好友不需要 Client。"""
    clients_by_name = {client.username: client for client in clients}
    owned = [member for member in party_config if member.controlled]

    missing = [
        member.username
        for member in owned
        if member.username not in clients_by_name
    ]
    if missing:
        print(f"任务引用了不存在的自有角色：{', '.join(missing)}")
        return None

    return [clients_by_name[member.username] for member in owned]



@dataclass(frozen=True)
class ResumeMatch:
    preset_key: str
    dungeon_id: str
    error: str = field(default="",compare=False)


def _preset_matches_dungeon(
    preset: DungeonPreset,
    data: dict[str, Any],
    *,
    check_difficulty:bool=True,
    check_event_overrides:bool=True,
) -> bool:
    """判断服务器上的 exploring 地下城是否属于某个预设。"""
    if data.get("status") != "exploring":
        return False

    if data.get("preset_id") != preset.preset_id:
        return False

    if check_event_overrides:
        nodes=data.get("nodes")
        runtime_choices={}
        if isinstance(nodes,list):
            runtime_choices={
                node["event_id"]:node["event_choice"]
                for node in nodes
                if (
                    isinstance(node,dict)
                    and isinstance(node.get("event_id"),str)
                    and isinstance(node.get("event_choice"),int)
                    and not isinstance(node.get("event_choice"),bool)
                )
            }
        for event_id,choice_index in preset.event_overrides.items():
            if event_id in runtime_choices and runtime_choices[event_id]!=choice_index:
                return False

    if check_difficulty and data.get("difficulty_label")!=preset.difficulty:
        return False

    if data.get("leader_id") not in {
        preset.opener.username,preset.leader.username
    }:
        return False

    members = data.get("members")
    if not isinstance(members, list):
        return False

    actual_members = {
        member.get("key")
        for member in members
        if isinstance(member, dict) and isinstance(member.get("key"), str)
    }
    required_members=set(preset.runtime_member_usernames)
    allowed_members=set(preset.member_usernames)
    return required_members<=actual_members<=allowed_members


def detect_resume_match(
    clients: list[AetherClient],
    presets: dict[str, DungeonPreset],
    *,
    expected_preset_key:str|None=None,
    expected_dungeon_id:str|None=None,
    allow_legacy_adopt:bool=False,
) -> ResumeMatch | None:
    """检测并恢复服务器上的 exploring 地下城状态。"""
    active_by_user: dict[str, dict[str, Any]] = {}
    query_errors=[]

    for client in clients:
        result = client.get_current_dungeon(silent=True)
        if not isinstance(result, dict) or result.get("code",0)!=0 or "data" not in result:
            query_errors.append(client.username)
            continue

        data = result.get("data")
        if data is not None and not isinstance(data,dict):
            query_errors.append(client.username)
            continue
        if not isinstance(data, dict):
            continue

        if data.get("status") in {"lobby", "exploring"} and not data.get("completion_reason"):
            active_by_user[client.username] = data

    if query_errors:
        return ResumeMatch("","",error="当前地下城查询失败，不能判断是否结束："+ "，".join(query_errors))
    if not active_by_user:
        return None

    dungeon_ids = {
        str(data.get("dungeon_id"))
        for data in active_by_user.values()
        if data.get("dungeon_id")
    }

    if len(dungeon_ids) != 1:
        print("检测到多个未结束地下城，无法安全恢复：")
        for username, data in active_by_user.items():
            print(
                f"  {username}: "
                f"id={data.get('dungeon_id')} "
                f"status={data.get('status')} "
                f"preset={data.get('preset_id')}"
            )
        return ResumeMatch(preset_key="", dungeon_id="")

    dungeon_id = next(iter(dungeon_ids))
    sample = next(iter(active_by_user.values()))

    if expected_dungeon_id is not None:
        preset=presets.get(expected_preset_key or "")
        if (
            dungeon_id!=expected_dungeon_id
            or preset is None
            or any(
                data.get("status")!="exploring"
                for data in active_by_user.values()
            )
            or set(preset.runtime_owned_usernames)-set(active_by_user)
        ):
            print(
                "进行中的地下城与 checkpoint ID 不一致："
                f"预期={expected_dungeon_id!r}，实际={dungeon_id!r}"
            )
            return ResumeMatch(
                preset_key="",dungeon_id=dungeon_id,
                error=f"恢复状态不一致：记录地下城={expected_dungeon_id}，当前地下城={dungeon_id}；请检查队长及在队成员" if dungeon_id==expected_dungeon_id else f"角色已在另一地下城：记录={expected_dungeon_id}，当前={dungeon_id}；不会续跑或重建旧任务",
            )
        print(
            f"按 checkpoint ID 恢复：{preset.label} "
            f"[{expected_preset_key}]，地下城 {dungeon_id}"
        )
        return ResumeMatch(
            preset_key=expected_preset_key or "",
            dungeon_id=dungeon_id,
        )

    if sample.get("status") == "lobby":
        print(
            "检测到尚未进入的 lobby 地下城。"
            "当前只自动续跑 exploring 状态，程序停止。"
        )
        return ResumeMatch(preset_key="", dungeon_id=dungeon_id)

    if allow_legacy_adopt and expected_preset_key is not None:
        preset=presets.get(expected_preset_key)
        if (
            preset is not None
            and _preset_matches_dungeon(
                preset,
                sample,
                check_difficulty=False,
                check_event_overrides=False,
            )
            and not (
                set(preset.runtime_owned_usernames)-set(active_by_user)
            )
        ):
            print(
                f"旧 checkpoint 已绑定地下城 ID：{preset.label} "
                f"[{expected_preset_key}]，地下城 {dungeon_id}"
            )
            return ResumeMatch(
                preset_key=expected_preset_key,
                dungeon_id=dungeon_id,
            )

    for key, preset in presets.items():
        if not _preset_matches_dungeon(preset, sample):
            continue

        expected_users = set(preset.runtime_owned_usernames)
        missing = expected_users - set(active_by_user)

        if missing:
            print(
                "进行中的地下城缺少预设成员状态："
                + ", ".join(sorted(missing))
            )
            return ResumeMatch(preset_key="", dungeon_id=dungeon_id)

        wrong_dungeon = [
            username
            for username in expected_users
            if str(active_by_user[username].get("dungeon_id")) != dungeon_id
        ]

        if wrong_dungeon:
            print(
                "预设成员处于不同地下城："
                + ", ".join(sorted(wrong_dungeon))
            )
            return ResumeMatch(preset_key="", dungeon_id=dungeon_id)

        print(
            f"检测到可恢复预设：{preset.label} "
            f"[{key}]，地下城 {dungeon_id}"
        )
        return ResumeMatch(preset_key=key, dungeon_id=dungeon_id)

    print(
        "检测到正在探索的地下城，但无法匹配当前任何预设：\n"
        f"  preset_id={sample.get('preset_id')}\n"
        f"  difficulty={sample.get('difficulty_label')}\n"
        f"  leader={sample.get('leader_id')}\n"
        f"  dungeon_id={dungeon_id}"
    )
    return ResumeMatch(preset_key="", dungeon_id=dungeon_id)


def execute_preset(
    clients: list[AetherClient],
    preset: DungeonPreset,
    *,
    resume: bool = False,
    hooks: RuntimeHooks | None = None,
    fast_mode: bool = False,
    acceleration_mode: AccelerationMode | None = None,
    accel_min_wait_seconds: float | None = None,
    accel_ticket_reserve: int | None = None,
    skip_camp_wait: bool | None = None,
) -> bool:
    """执行一个且仅一个地下城预设。"""
    hooks = hooks or RuntimeHooks()
    layout_rules=load_layout_rules()
    notifier = NtfyNotifier(preset)
    resolved_acceleration = (
        acceleration_mode
        if acceleration_mode is not None
        else ("always" if fast_mode else "never")
    )
    resolved_skip_camp = (
        fast_mode if skip_camp_wait is None else bool(skip_camp_wait)
    )

    hooks.state(
        "starting",
        preset_key=preset.key,
        preset_label=preset.label,
        fast_mode=fast_mode,
        acceleration_mode=resolved_acceleration,
        skip_camp_wait=resolved_skip_camp,
    )
    party_text = " -> ".join(
        (
            member.username
            if member.controlled
            else f"{member.username}(离线好友)"
        )
        for member in preset.party
    )
    preset_text = ", ".join(
        f"{member.username}={member.preset_index}"
        for member in preset.owned_members
    )

    print(
        f"\n准备运行：{preset.label}"
        f"{' [快速模式]' if fast_mode else ''}\n"
        f"  key：{preset.key}\n"
        f"  队伍站位：{party_text}\n"
        f"  实际队长：{preset.leader.username}\n"
        f"  角色预设：{preset_text}\n"
        f"  战斗加速：{resolved_acceleration}\n"
        f"  营地等待：{'跳过' if resolved_skip_camp else '保留'}"
    )

    party_config=preset.runtime_members if resume else preset.party
    party = select_party(clients,party_config)
    if party is None:
        notifier.error("队伍配置异常，无法开始")
        return False

    if resume:
        print("发现服务器上的未完成探索，直接从当前节点续跑")
    else:
        if not create_party(party,preset,hooks,layout_rules=layout_rules):
            print("地下城创建/组队出现故障")
            notifier.error(
                append_error_detail(
                    "地下城创建/组队出现故障",
                    get_latest_client_error(party),
                )
            )
            return False

    runner = DungeonRunner(
        party,
        preset,
        hooks=hooks,
        fast_mode=fast_mode,
        acceleration_mode=resolved_acceleration,
        accel_min_wait_seconds=accel_min_wait_seconds,
        accel_ticket_reserve=accel_ticket_reserve,
        skip_camp_wait=resolved_skip_camp,
        resume=resume,
    )
    if not runner.run(resume=resume):
        print("地下城探索出现故障、暂停或主动撤退")
        return False

    print(f"{preset.label} 探索完毕")
    hooks.state("completed", preset_key=preset.key, preset_label=preset.label)
    hooks.emit(f"Aether：{preset.label} 探索完毕。")
    return True


def run_preset(
    preset_key: str,
    *,
    clients: list[AetherClient] | None = None,
    hooks: RuntimeHooks | None = None,
    allow_password_prompt: bool = False,
    fast_mode: bool = False,
    acceleration_mode: AccelerationMode | None = None,
    accel_min_wait_seconds: float | None = None,
    accel_ticket_reserve: int | None = None,
    skip_camp_wait: bool | None = None,
    resume_only:bool=False,
    expected_dungeon_id:str|None=None,
) -> bool:
    """按稳定 key 运行单个预设。

    以后 QQ Bot 可以直接调用：
        run_preset("red_leaf_extreme")
    """
    preset = DUNGEON_PRESETS.get(preset_key)

    if preset is None:
        print(f"不存在地下城预设：{preset_key}")
        return False

    hooks = hooks or RuntimeHooks()

    if clients is None:
        accounts = [
            Account(username=username)
            for username in preset.owned_usernames
        ]
        clients = login_all_accounts(
            accounts,
            allow_password_prompt=allow_password_prompt,
            password_provider=hooks.request_password,
        )
        if clients is None:
            return False

    # 已完成队伍交接的恢复任务不再占用已退出的开本角色。
    party_config=preset.runtime_members if resume_only else preset.party
    selected_clients = select_party(clients,party_config)
    if selected_clients is None:
        return False
    clients = selected_clients

    resume_match=detect_resume_match(
        clients,
        DUNGEON_PRESETS,
        expected_preset_key=preset_key if expected_dungeon_id else None,
        expected_dungeon_id=expected_dungeon_id,
    )

    if resume_only and resume_match is None:
        print("恢复任务未找到对应的进行中地下城")
        return False

    if resume_match is not None:
        if not resume_match.preset_key:
            print("存在未结束地下城，但无法安全恢复")
            return False

        if resume_match.preset_key != preset_key:
            active = DUNGEON_PRESETS[resume_match.preset_key]
            print(
                f"当前已有未完成探索：{active.label} "
                f"[{resume_match.preset_key}]\n"
                f"不能同时启动：{preset.label} [{preset_key}]"
            )
            return False

        return execute_preset(
            clients,
            preset,
            resume=True,
            hooks=hooks,
            fast_mode=fast_mode,
            acceleration_mode=acceleration_mode,
            accel_min_wait_seconds=accel_min_wait_seconds,
            accel_ticket_reserve=accel_ticket_reserve,
            skip_camp_wait=skip_camp_wait,
        )

    return execute_preset(
        clients,
        preset,
        resume=False,
        hooks=hooks,
        fast_mode=fast_mode,
        acceleration_mode=acceleration_mode,
        accel_min_wait_seconds=accel_min_wait_seconds,
        accel_ticket_reserve=accel_ticket_reserve,
        skip_camp_wait=skip_camp_wait,
    )
