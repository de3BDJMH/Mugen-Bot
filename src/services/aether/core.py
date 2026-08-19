from __future__ import annotations

import getpass
import json
import os
import pathlib
import pickle
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal
from urllib.parse import quote

import requests

from . import config as cfg


# =========================
# 基础配置
# =========================

BASE_URL = "https://chiyuki.diving-fish.com/api/aether"
WEB_URL = "https://chiyuki.diving-fish.com/aether/"
REQUEST_TIMEOUT = 10
PARTY_ACTION_DELAY = 0.5
DUNGEON_REROLL_DELAY = 2.0
BATTLE_FINISH_BUFFER = 3

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
    "status": "/status",
    "preset_apply": "/status/presets/apply",
    "dungeon_search": "/dungeon/search",
    "dungeon_disband": "/dungeon/disband",
    "dungeon_join": "/dungeon/join",
    "dungeon_reorder": "/dungeon/reorder",
    "dungeon_current": "/dungeon/current",
    "dungeon_enter": "/dungeon/enter",
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
class DungeonPreset:
    """一次独立地下城运行所需的完整预设。

    key 是稳定标识，适合 CLI / QQ Bot 直接引用；
    name 是展示名，可以随时修改。
    party 中每一项为 (用户名, 角色预设槽位)，第一项是队长。
    layout_rule 指向 DUNGEON_LAYOUT_RULES 中的一套筛图规则。
    """

    key: str
    name: str
    preset_id: str
    difficulty: str
    party: tuple[tuple[str, int], ...]
    visibility: str = "private"
    layout_rule: str | None = None

    @property
    def label(self) -> str:
        return self.name


# =========================
# 配置加载
# =========================


def load_layout_rules() -> dict[str, LayoutRule]:
    rules: dict[str, LayoutRule] = {}

    for preset_id, raw in cfg.DUNGEON_LAYOUT_RULES.items():
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
) -> tuple[tuple[str, int], ...]:
    if not isinstance(raw_party, (list, tuple)):
        raise TypeError(f"{context} 的 party 必须是 list/tuple")

    party: list[tuple[str, int]] = []

    for member in raw_party:
        if not isinstance(member, (list, tuple)) or len(member) != 2:
            raise TypeError(
                f"{context} 的 party 成员必须是 (用户名, 预设槽位)"
            )

        username, preset_index = member
        preset_index = int(preset_index)

        if not 0 <= preset_index <= 4:
            raise ValueError(
                f"{context}：{username} 的预设槽位必须在 0~4"
            )

        party.append((str(username), preset_index))

    if not party:
        raise ValueError(f"{context} 的 party 不能为空")

    return tuple(party)


def load_dungeon_presets() -> dict[str, DungeonPreset]:
    """读取独立地下城预设。

    优先读取新版 DUNGEON_PRESETS。

    如果用户仍保留旧 DUNGEON_TASKS，则自动兼容成独立预设，
    避免升级主程序时必须立刻重写配置。
    """
    raw_presets = getattr(cfg, "DUNGEON_PRESETS", None)

    if raw_presets is not None:
        if not isinstance(raw_presets, dict):
            raise TypeError("DUNGEON_PRESETS 必须是 dict")

        presets: dict[str, DungeonPreset] = {}

        for raw_key, raw in raw_presets.items():
            key = str(raw_key)

            if not isinstance(raw, dict):
                raise TypeError(f"预设 {key!r} 必须是 dict")

            preset_id = str(raw["preset_id"])
            difficulty = str(raw["difficulty"])
            default_name = (
                f"{cfg.PRESET_NAMES.get(preset_id, preset_id)} · {difficulty}"
            )

            presets[key] = DungeonPreset(
                key=key,
                name=str(raw.get("name") or default_name),
                preset_id=preset_id,
                difficulty=difficulty,
                party=_parse_party(
                    raw.get("party"),
                    context=f"预设 {key!r}",
                ),
                visibility=str(raw.get("visibility", "private")),
                layout_rule=(
                    None
                    if raw.get("layout_rule") is None
                    else str(raw["layout_rule"])
                ),
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
                f"{cfg.PRESET_NAMES.get(preset_id, preset_id)} · "
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
        )

    return presets


DUNGEON_LAYOUT_RULES = load_layout_rules()
DUNGEON_PRESETS = load_dungeon_presets()


# =========================
# API 客户端
# =========================


class AetherClient:
    """单个 Aether 账号的 HTTP API 客户端。

    这里只负责“如何请求服务器”，不负责决定事件选什么、商店买什么、分支走哪条。
    """

    def __init__(self, account: Account, cookie_file: pathlib.Path | None = None):
        self.session = requests.Session()
        self.username = account.username
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
            response = self.session.get(self._url("status"), timeout=5)
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

    def search_dungeon(self, difficulty: str, preset_id: str, visibility: str) -> bool:
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

        print(
            f"{cfg.PRESET_NAMES.get(preset_id, preset_id)} · {difficulty} 搜索成功\n"
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
    config_name: str,
    env_name: str,
    default: str | None = None,
) -> str | None:
    """优先读取环境变量，其次读取 config.py；未配置则返回默认值。"""
    env_value = os.getenv(env_name)
    if env_value is not None:
        value = env_value.strip()
        return value or default

    raw = getattr(cfg, config_name, default)
    if raw is None:
        return default

    value = str(raw).strip()
    return value or default


class NtfyNotifier:
    """给 Aether 运行过程发送独立 ntfy 推送。

    只要 NTFY_TOPIC / AETHER_NTFY_TOPIC 没配置，就完全禁用。
    推送使用 daemon thread，不阻塞地下城主流程。
    """

    def __init__(self, preset: DungeonPreset):
        self.preset = preset
        self.topic = _ntfy_setting(
            "NTFY_TOPIC",
            "AETHER_NTFY_TOPIC",
        )
        self.server = (
            _ntfy_setting(
                "NTFY_SERVER",
                "AETHER_NTFY_SERVER",
                "https://ntfy.sh",
            )
            or "https://ntfy.sh"
        ).rstrip("/")
        self.token = _ntfy_setting(
            "NTFY_TOKEN",
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
# 运行时事件选择记忆
# =========================

_EVENT_CHOICES_FILE = pathlib.Path(cfg.AETHER_DATA_DIR) / "event_choices.json"
_EVENT_CHOICES_LOCK = threading.Lock()


def _load_learned_event_choices_unlocked() -> dict[str, dict[str, Any]]:
    """读取运行过程中记住的事件选择。

    文件损坏时保守地忽略，不影响 Bot 启动。
    """
    if not _EVENT_CHOICES_FILE.exists():
        return {}

    try:
        with _EVENT_CHOICES_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        print(f"读取事件记忆失败：{_EVENT_CHOICES_FILE}")
        return {}

    if not isinstance(data, dict):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for event_id, record in data.items():
        if isinstance(record, dict):
            result[str(event_id)] = record

    return result


def get_learned_event_choice(event_id: str) -> tuple[str, int] | None:
    """读取某个由 QQ 交互学习到的事件选择。"""
    event_id = str(event_id)

    with _EVENT_CHOICES_LOCK:
        choices = _load_learned_event_choices_unlocked()

    record = choices.get(event_id)
    if not isinstance(record, dict):
        return None

    choice_index = record.get("choice_index")
    if not isinstance(choice_index, int) or choice_index < 0:
        return None

    choice_name = record.get("choice_name")
    if not isinstance(choice_name, str) or not choice_name:
        choice_name = f"选项 {choice_index}"

    return choice_name, choice_index


def save_learned_event_choice(
    event: UnknownEvent,
    choice_index: int,
) -> bool:
    """把一次成功执行的未知事件选择写入 data/aether/event_choices.json。"""
    if not event.event_id or choice_index < 0:
        return False

    choice_name = (
        event.options[choice_index]
        if 0 <= choice_index < len(event.options)
        else f"选项 {choice_index}"
    )

    record = {
        "event_name": event.event_name,
        "choice_index": choice_index,
        "choice_name": choice_name,
    }

    try:
        with _EVENT_CHOICES_LOCK:
            choices = _load_learned_event_choices_unlocked()
            choices[event.event_id] = record

            _EVENT_CHOICES_FILE.parent.mkdir(parents=True, exist_ok=True)

            # 先写临时文件再 replace，避免进程中断留下半截 JSON。
            temp_file = _EVENT_CHOICES_FILE.with_suffix(".json.tmp")
            with temp_file.open("w", encoding="utf-8") as file:
                json.dump(
                    choices,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                file.write("\n")

            temp_file.replace(_EVENT_CHOICES_FILE)

    except OSError as exc:
        print(f"保存事件记忆失败：{exc}")
        return False

    return True


# =========================
# 策略
# =========================


class DungeonStrategy:
    """只负责“遇到某种情况该怎么选”，不发送 HTTP 请求。"""

    @staticmethod
    def get_event_choice(event_id: str) -> tuple[str, int] | None:
        event_id = str(event_id)

        # 手工配置始终拥有最高优先级，便于你以后覆盖错误的学习结果。
        configured = cfg.EVENT_CHOICES.get(event_id)
        if configured is not None:
            return configured

        learned = get_learned_event_choice(event_id)
        if learned is not None:
            print(
                f"事件 {event_id} 使用已记住的选择："
                f"{learned[0]} ({learned[1]})"
            )
            return learned

        return None

    @staticmethod
    def get_branch_choice(preset_id: str) -> int | None:
        return cfg.BRANCH_CHOICES.get(preset_id)

    @staticmethod
    def should_buy(item_name: str) -> bool:
        if any(marker in item_name for marker in cfg.SHOP_BUY_ALWAYS_CONTAINS):
            return True

        if cfg.SHOP_BUY_THREE_STAR_MARKER in item_name:
            return not any(
                excluded in item_name
                for excluded in cfg.SHOP_BUY_THREE_STAR_EXCLUDES
            )

        return False

    @staticmethod
    def should_retreat_from_battle(battle_preset: str | None) -> bool:
        return battle_preset in cfg.RETREAT_BATTLE_PRESETS


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
    ):
        if not party:
            raise ValueError("队伍不能为空")

        self.party = party
        self.captain = party[0]
        self.preset = preset
        self.strategy = strategy or DungeonStrategy()
        self.hooks = hooks or RuntimeHooks()
        self.fast_mode = fast_mode
        self.notifier = NtfyNotifier(preset)

        # 快速模式第一次遇到战斗时才查询三个账号的真实库存。
        # 后续每成功使用一张就在内存里 -1，避免每场战斗都请求三个
        # 体积很大的 /status 响应。
        self._accel_ticket_counts: dict[str, int] | None = None

    def run(self, *, resume: bool = False) -> bool:
        dungeon = self.captain.get_current_dungeon()
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
                f"{cfg.PRESET_NAMES.get(self.preset.preset_id, self.preset.preset_id)} "
                f"· {self.preset.difficulty}"
            )
        else:
            if not self.captain.enter_dungeon():
                self.notifier.error(
                    self._append_error_detail(
                        "进入地下城失败",
                        self.captain.last_error,
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
            return self._handle_shop(data)
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
        """选择当前加速券最多的队员。

        数量并列时，max() 保留 party 中最先出现的成员，
        因此并列规则稳定且可预测。
        """
        counts = self._accel_ticket_counts
        if counts is None:
            counts = self._load_accel_ticket_counts()

        candidates = [
            member
            for member in self.party
            if counts.get(member.username, 0) > 0
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
        battle_preset = node_data.get("battle_preset")

        accelerator: AetherClient | None = None
        accelerator_before = 0

        if self.fast_mode:
            selected = self._choose_accelerator()
            if selected is None:
                print(
                    "快速模式：三个账号都没有可用加速券，"
                    "本场自动改为普通等待"
                )
                self.hooks.state("battle")
            else:
                accelerator, accelerator_before = selected
                self.hooks.state(
                    "battle_accelerating",
                    accelerator=accelerator.username,
                    tickets=accelerator_before,
                )
                print(
                    f"快速模式：本场由 {accelerator.username} 使用加速券"
                    f"（当前 {accelerator_before} 张）"
                )
        else:
            self.hooks.state("battle")

        # 普通模式仍保留原来的指定战斗撤退策略。
        # 快速模式即使暂时无券，也不因为 RETREAT_BATTLE_PRESETS 改变策略；
        # 它只是这一场退化为普通等待。
        if (
            not self.fast_mode
            and self.strategy.should_retreat_from_battle(battle_preset)
        ):
            print(f"遇到需要撤退的战斗：{battle_preset}")
            self.captain.retreat_dungeon()
            return False

        # 战斗仍由队长负责 start。
        battle = self.captain.start_battle()
        if battle is None:
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

        if accelerator is not None:
            # 加速接口无 payload，消耗的是“发送这个请求的账号”的券。
            # 因此这里故意使用被选中队员自己的 Session，而不是固定 captain。
            if not accelerator.accelerate_battle():
                return False

            # 只有服务器确认 accelerate 成功后才修改本地库存，
            # 避免网络/400 错误造成虚假扣券。
            self._mark_accel_ticket_used(accelerator.username)
            remaining = self._accel_ticket_counts.get(
                accelerator.username,
                0,
            ) if self._accel_ticket_counts is not None else 0
            print(
                f"{accelerator.username} 加速券剩余（本地缓存）："
                f"{remaining}"
            )

            # accelerate 只完成 battle_status。
            # 节点仍需队长读取结果并 complete 正式结算。
            result = self.captain.get_current_node()
            if result is None:
                return False

            self._print_battle_result(result)
            return self.captain.complete_battle()

        # 普通模式，或快速模式但全队无券：正常等待。
        time.sleep(max(0.0, battle.wait_time + BATTLE_FINISH_BUFFER))

        result = self.captain.get_current_node()
        if result is None:
            return False

        self._print_battle_result(result)
        return self.captain.complete_battle()

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

        if self.fast_mode:
            print("快速模式：已进入营地，跳过停留等待并立即离开")
            self.hooks.state("camp_accelerated")
            return self.captain.leave_camp()

        print(f"营地停留 {cfg.CAMP_STAY_TIME} 秒")
        time.sleep(cfg.CAMP_STAY_TIME)

        return self.captain.leave_camp()

    def _handle_event(self, node_data: dict[str, Any]) -> bool:
        event = node_data.get("event")
        if not isinstance(event, dict):
            print(f"事件数据结构异常：{node_data}")
            return False

        event_id = event.get("id")
        event_name = event.get("name", event_id)
        choice = self.strategy.get_event_choice(event_id)
        learned_event: UnknownEvent | None = None

        if choice is None:
            raw_options = event.get("choices")
            if not isinstance(raw_options, list):
                raw_options = event.get("options")
            if not isinstance(raw_options, list):
                raw_options = []

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

        # 只有本次原本是未知事件，并且服务器已经确认选择成功，
        # 才把 QQ 选择记下来。
        if learned_event is not None:
            if save_learned_event_choice(learned_event, choice_index):
                print(
                    f"已记住事件选择："
                    f"{learned_event.event_id} -> {choice_index}"
                )
                self.hooks.emit(
                    f"Aether：已记住「{learned_event.event_name}」"
                    f"选择 {choice_index}，以后将自动处理。"
                )
            else:
                self.hooks.emit(
                    f"Aether：事件已处理，但「{learned_event.event_name}」"
                    "的选择未能写入事件记忆文件。"
                )

        self.hooks.state("event_resolved")
        return True

    def _handle_shop(self, node_data: dict[str, Any]) -> bool:
        player_shops = node_data.get("player_shops")
        if not isinstance(player_shops, dict):
            print("商店数据中缺少 player_shops")
            return False

        own_items = player_shops.get(self.captain.username)
        if not self._maybe_buy_third_item(own_items):
            return False

        for member in self.party[1:]:
            shop = self.captain.get_shop(member.username)
            if shop is None:
                return False

            shop_items = shop.get("data", {}).get("shop_items")
            if not self._maybe_buy_third_item(shop_items, target_username=member.username):
                return False

        return self.captain.leave_shop()

    def _maybe_buy_third_item(
        self,
        items: Any,
        *,
        target_username: str | None = None,
    ) -> bool:
        """保留旧策略：只检查商店第 3 个物品，需要时购买。"""
        if not isinstance(items, list) or len(items) <= 2:
            print(f"商店物品列表异常：{items!r}")
            return False

        item = items[2]
        if not isinstance(item, dict):
            print(f"商店物品数据异常：{item!r}")
            return False

        item_name = str(item.get("name", ""))
        if not self.strategy.should_buy(item_name):
            return True

        return self.captain.buy_item(
            2,
            target_username=target_username,
        )

    def _handle_branch(self) -> bool:
        choice_index = self.strategy.get_branch_choice(self.preset.preset_id)
        if choice_index is None:
            print(f"副本 {self.preset.preset_id} 没有配置分支选择，停止自动探索")
            return False
        return self.captain.choose_branch(choice_index)


# =========================
# 组队与任务调度
# =========================


def load_accounts() -> list[Account]:
    """只读取账号名，不在这里主动询问密码。

    登录顺序由 login_all_accounts() 决定：
    1. 先尝试每个账号自己的 Cookie；
    2. Cookie 无效时才使用 AETHER_PASSWORD；
    3. 环境变量也没有时，才在终端询问一次共享密码。
    """
    password = os.getenv("AETHER_PASSWORD")
    return [
        Account(username=username, password=password)
        for username in cfg.ACCOUNT_USERNAMES
    ]


def login_all_accounts(
    accounts: list[Account],
    *,
    allow_password_prompt: bool = True,
    password_provider: Callable[[str], str | None] | None = None,
) -> list[AetherClient] | None:
    """Cookie 优先登录全部账号。

    登录顺序：
    1. 每个账号先尝试 Cookie；
    2. Cookie 失效时优先复用已有 shared_password；
    3. 没有密码时，如果提供了 password_provider（Bot 模式），
       就阻塞等待 QQ 侧提交密码；
    4. 只有 CLI 模式才允许 getpass()；
    5. 登录成功后更新 Cookie，后续失效账号复用同一个密码。
    """
    clients: list[AetherClient] = []

    # 如果环境变量 AETHER_PASSWORD 已经存在，Account.password 会带进来。
    shared_password = next(
        (account.password for account in accounts if account.password),
        None,
    )

    for account in accounts:
        client = AetherClient(account)

        # 第一优先级：Cookie。
        if client.try_cookie_login():
            clients.append(client)
            continue

        # Cookie 失效且当前还没有密码。
        if not shared_password:
            if password_provider is not None:
                # Bot 模式：
                # 这里运行在 asyncio.to_thread() 的工作线程中。
                # password_provider 会一直等到 QQ 侧调用 submit_password()。
                shared_password = password_provider(account.username)

                if not shared_password:
                    print(
                        f"{account.username} Cookie 已失效，"
                        "QQ 侧未提供密码，停止登录"
                    )
                    return None

            elif allow_password_prompt:
                # CLI 模式才允许从终端输入。
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
) -> bool:
    """队长搜索地下城，其他成员加入，并按任务中声明的顺序排列。"""
    if not party:
        print("队伍不能为空")
        return False

    captain = party[0]

    # 每个账号使用任务中为自己指定的预设槽位。
    preset_by_username = dict(preset.party)

    for member in party:
        preset_index = preset_by_username[member.username]
        if not 0 <= preset_index <= 4:
            print(
                f"{member.username} 的预设槽位无效：{preset_index}，"
                "必须在 0~4 之间"
            )
            return False

        if not member.apply_preset(preset_index):
            print(f"{member.username} 切换预设失败，停止创建队伍")
            return False

        time.sleep(PARTY_ACTION_DELAY)

    if not search_acceptable_dungeon(captain, preset, hooks):
        print("没有取得可接受的地下城布局，无法继续后续操作")
        return False

    if captain.dungeon_id is None:
        print("筛图结束但没有取得 dungeon_id，停止执行")
        return False

    time.sleep(PARTY_ACTION_DELAY)
    for member in party[1:]:
        if not member.join_dungeon(captain.dungeon_id):
            print("有队员未能成功加入队伍，请检查")
            return False

    time.sleep(PARTY_ACTION_DELAY)
    return reorder_party(captain, tuple(username for username, _ in preset.party))


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
    rule = DUNGEON_LAYOUT_RULES.get(rule_name)

    # 没有配置规则时保持普通搜索行为。
    if rule is None:
        return captain.search_dungeon(
            preset.difficulty,
            preset.preset_id,
            preset.visibility,
        )

    attempt = 0

    while True:
        attempt += 1

        if not captain.search_dungeon(
            preset.difficulty,
            preset.preset_id,
            preset.visibility,
        ):
            return False

        if captain.dungeon_id is None:
            print("搜索成功但没有取得 dungeon_id")
            return False

        score, counts = score_search_layout(captain, rule)
        layout = summarize_search_layout(captain)

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
            )

            if hooks.choose_layout is None:
                # 非交互调用时保持保守：接受第一张，不死等 stdin。
                decision = "accept"
            else:
                decision = hooks.choose_layout(candidate)

            if decision == "accept":
                print("接受当前布局")
                hooks.state("layout_accepted", score=score)
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
            return True

        print(f"  低于最低接受分 {rule.min_score:g}")

        max_attempts = max(1, rule.max_attempts)
        if attempt >= max_attempts:
            if rule.accept_last_on_exhausted:
                print("  已达到最大刷新次数，接受最后一张布局")
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
    party_config: tuple[tuple[str, int], ...],
) -> list[AetherClient] | None:
    """按任务中声明的用户名顺序选择队伍。"""
    clients_by_name = {client.username: client for client in clients}
    usernames = tuple(username for username, _ in party_config)

    missing = [username for username in usernames if username not in clients_by_name]
    if missing:
        print(f"任务引用了不存在的账号：{', '.join(missing)}")
        return None

    if len(set(usernames)) != len(usernames):
        print(f"任务中的队伍成员重复：{usernames}")
        return None

    return [clients_by_name[username] for username in usernames]




@dataclass(frozen=True)
class ResumeMatch:
    preset_key: str
    dungeon_id: str


def _preset_matches_dungeon(
    preset: DungeonPreset,
    data: dict[str, Any],
) -> bool:
    """判断服务器上的 exploring 地下城是否属于某个预设。"""
    if data.get("status") != "exploring":
        return False

    if data.get("preset_id") != preset.preset_id:
        return False

    if data.get("difficulty_label") != preset.difficulty:
        return False

    if data.get("leader_id") != preset.party[0][0]:
        return False

    members = data.get("members")
    if not isinstance(members, list):
        return False

    actual_members = {
        member.get("key")
        for member in members
        if isinstance(member, dict) and isinstance(member.get("key"), str)
    }
    expected_members = {username for username, _ in preset.party}

    return actual_members == expected_members


def detect_resume_match(
    clients: list[AetherClient],
    presets: dict[str, DungeonPreset],
) -> ResumeMatch | None:
    """检测并恢复服务器上的 exploring 地下城状态。"""
    active_by_user: dict[str, dict[str, Any]] = {}

    for client in clients:
        result = client.get_current_dungeon(silent=True)
        if not isinstance(result, dict):
            continue

        data = result.get("data")
        if not isinstance(data, dict):
            continue

        if data.get("status") in {"lobby", "exploring"}:
            active_by_user[client.username] = data

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

    if sample.get("status") == "lobby":
        print(
            "检测到尚未进入的 lobby 地下城。"
            "当前只自动续跑 exploring 状态，程序停止。"
        )
        return ResumeMatch(preset_key="", dungeon_id=dungeon_id)

    for key, preset in presets.items():
        if not _preset_matches_dungeon(preset, sample):
            continue

        expected_users = {username for username, _ in preset.party}
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
) -> bool:
    """执行一个且仅一个地下城预设。"""
    hooks = hooks or RuntimeHooks()
    notifier = NtfyNotifier(preset)
    hooks.state(
        "starting",
        preset_key=preset.key,
        preset_label=preset.label,
        fast_mode=fast_mode,
    )
    print(
        f"\n准备运行：{preset.label}"
        f"{' [快速模式]' if fast_mode else ''}\n"
        f"  key：{preset.key}\n"
        f"  队伍：{' -> '.join(username for username, _ in preset.party)}\n"
        f"  角色预设："
        f"{', '.join(f'{username}={slot}' for username, slot in preset.party)}"
    )

    party = select_party(clients, preset.party)
    if party is None:
        notifier.error("队伍配置异常，无法开始")
        return False

    if resume:
        print("发现服务器上的未完成探索，直接从当前节点续跑")
    else:
        if not create_party(party, preset, hooks):
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
        accounts = load_accounts()
        clients = login_all_accounts(
            accounts,
            allow_password_prompt=allow_password_prompt,
            password_provider=hooks.request_password,
        )
        if clients is None:
            return False

    resume_match = detect_resume_match(clients, DUNGEON_PRESETS)

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

        return execute_preset(clients, preset, resume=True, hooks=hooks, fast_mode=fast_mode)

    return execute_preset(clients, preset, resume=False, hooks=hooks, fast_mode=fast_mode)
