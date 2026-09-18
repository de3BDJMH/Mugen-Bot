from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from .core import (
    DUNGEON_PRESETS,
    LayoutCandidate,
    RuntimeHooks,
    UnknownEvent,
    load_dungeon_presets,
    normalize_runtime_nodes,
    reload_dungeon_presets,
    run_preset,
)
from src.storage.aether import AetherConfigError
from .scheduler import AetherTaskScheduler

Notifier = Callable[[str], Awaitable[None]]


@dataclass
class ManagerStatus:
    running: bool = False
    preset_key: str | None = None
    preset_label: str | None = None
    fast_mode: bool = False
    phase: str = "idle"
    node_name: str | None = None
    node_index: int | None = None
    nodes: tuple[dict[str, Any], ...] = ()
    started_at: float | None = None
    last_message: str | None = None
    pending_kind: str | None = None


@dataclass
class _PendingDecision:
    kind: Literal["layout", "event", "password"]
    event: threading.Event
    payload: Any
    result: Any = None


class AetherManager:
    """NoneBot 侧的单任务调度器。

    Aether 核心仍然是同步 requests + sleep。
    Manager 用 asyncio.to_thread 把整次地下城放到工作线程，
    因此不会阻塞 NoneBot 主事件循环。
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._notifier: Notifier | None = None

        self._status = ManagerStatus()
        self._status_lock = threading.Lock()

        self._pending: _PendingDecision | None = None
        self._pending_lock = threading.Lock()

        self._stop_requested = threading.Event()
        self.scheduler = AetherTaskScheduler()

    @property
    def single_running(self) -> bool:
        task = self._task
        return bool(task and not task.done())

    @property
    def running(self) -> bool:
        return self.single_running or self.scheduler.running

    def preset_items(self) -> list[tuple[str, str]]:
        return [(key,preset.label) for key,preset in load_dungeon_presets().items()]

    def resolve_preset(self, value: str) -> str | None:
        value = value.strip()

        items = self.preset_items()

        if any(value==key for key,_ in items):
            return value

        try:
            index = int(value)
        except ValueError:
            index = -1

        if 1 <= index <= len(items):
            return items[index - 1][0]

        # 也允许直接输入展示名。
        for key, label in items:
            if value == label:
                return key

        return None

    def preset_menu(self) -> str:
        items = self.preset_items()
        if not items:
            return "当前没有配置 Aether 地下城预设。"

        lines = ["请选择要运行的 Aether 地下城："]
        for index, (key, label) in enumerate(items, start=1):
            lines.append(f"{index}. {label} [{key}]")

        return "\n".join(lines)

    def task_plan_menu(self) -> str:
        return self.scheduler.plan_menu()

    def resolve_task_plan(self, value: str) -> str | None:
        return self.scheduler.resolve_plan(value)

    def resolve_task_run_mode(self, value: str | None) -> str | None:
        return self.scheduler.resolve_run_mode(value)

    async def start_task_plan(
        self,
        plan_key: str,
        notifier: Notifier,
        *,
        run_mode: str = "save",
    ) -> tuple[bool, str]:
        if self.running:
            return False, "已有 Aether 任务正在运行。"

        resolved_mode = self.scheduler.resolve_run_mode(run_mode)
        if resolved_mode is None:
            return False, f"未知批量运行模式：{run_mode}"

        return await self.scheduler.start(
            plan_key,
            notifier,
            run_mode=resolved_mode,
        )

    async def recover_task_plan(
        self,
        notifier: Notifier,
    ) -> tuple[bool, str]:
        if self.running:
            return False, "已有 Aether 任务正在运行。"
        return await self.scheduler.recover(notifier)

    def retry_task(self, sequence: int) -> tuple[bool, str]:
        return self.scheduler.retry_task(sequence)

    def skip_task(self, sequence: int) -> tuple[bool, str]:
        return self.scheduler.skip_task(sequence)

    async def start(
        self,
        preset_key: str,
        notifier: Notifier,
        *,
        fast_mode: bool = False,
    ) -> tuple[bool, str]:
        if self.running:
            return False, "已有 Aether 地下城任务正在运行。"

        try:
            presets=reload_dungeon_presets()
        except (AetherConfigError,KeyError,TypeError,ValueError) as exc:
            return False,f"Aether 地下城预设配置无效：{exc}"
        preset=presets.get(preset_key)
        if preset is None:
            return False, f"不存在 Aether 预设：{preset_key}"

        self._loop = asyncio.get_running_loop()
        self._notifier = notifier
        self._stop_requested.clear()

        with self._status_lock:
            self._status = ManagerStatus(
                running=True,
                preset_key=preset_key,
                preset_label=preset.label,
                fast_mode=fast_mode,
                phase="starting",
                started_at=time.time(),
            )

        self._task = asyncio.create_task(
            self._run_background(preset_key, fast_mode=fast_mode),
            name=f"aether:{preset_key}",
        )

        mode_text = "（快速模式）" if fast_mode else ""
        return True, f"已启动：{preset.label}{mode_text}"

    async def _run_background(
        self,
        preset_key: str,
        *,
        fast_mode: bool,
    ) -> None:
        try:
            result = await asyncio.to_thread(
                run_preset,
                preset_key,
                hooks=self._build_hooks(),
                allow_password_prompt=False,
                fast_mode=fast_mode,
            )

            if result:
                self._notify_from_loop("Aether 自动打本任务已结束：成功。",kind="summary")
            elif self._stop_requested.is_set():
                self._notify_from_loop("Aether 自动打本任务已按要求暂停。",kind="summary")
            else:
                self._notify_from_loop(
                    "Aether 自动打本任务已停止。可发送 /aether 状态 查看最后状态。"
                )
        except Exception as exc:
            self._notify_from_loop(f"Aether 后台任务异常：{type(exc).__name__}: {exc}")
            with self._status_lock:
                self._status.phase = "error"
                self._status.last_message = str(exc)
        finally:
            self._release_pending(default_result=None)

            with self._status_lock:
                self._status.running = False

    def _build_hooks(self) -> RuntimeHooks:
        return RuntimeHooks(
            choose_layout=self._wait_layout_decision,
            choose_unknown_event=self._wait_event_decision,
            request_password=self._wait_password,
            notify=lambda message:self._notify_from_thread(message,kind="detail"),
            on_state=self._on_state,
            should_stop=self._stop_requested.is_set,
        )

    def _on_state(self, phase: str, data: dict[str, Any]) -> None:
        with self._status_lock:
            self._status.phase = phase

            if data.get("preset_key"):
                self._status.preset_key = str(data["preset_key"])
            if data.get("preset_label"):
                self._status.preset_label = str(data["preset_label"])
            if "fast_mode" in data:
                self._status.fast_mode = bool(data["fast_mode"])
            if data.get("node_name") is not None:
                self._status.node_name = str(data["node_name"])
            if data.get("node_index") is not None:
                try:
                    self._status.node_index = int(data["node_index"])
                except (TypeError, ValueError):
                    pass
            if "nodes" in data:
                self._status.nodes = normalize_runtime_nodes(data["nodes"])

            if phase == "waiting_layout":
                self._status.pending_kind = "layout"
            elif phase == "waiting_event":
                self._status.pending_kind = "event"
            elif phase in {"layout_accepted", "event_resolved", "completed", "stopped"}:
                self._status.pending_kind = None

    def _notify_from_thread(self, message: str,*,kind:str="error") -> None:
        with self._status_lock:
            self._status.last_message = message

        loop = self._loop
        notifier = self._notifier

        if loop is None or notifier is None:
            return

        asyncio.run_coroutine_threadsafe(self._safe_notify(message,kind=kind), loop)

    def _notify_from_loop(self, message: str,*,kind:str="error") -> None:
        with self._status_lock:
            self._status.last_message = message

        loop = self._loop
        if loop is None:
            return

        loop.create_task(self._safe_notify(message,kind=kind))

    async def _safe_notify(self, message: str,*,kind:str="error") -> None:
        from .notifications import allows
        if not allows(kind):
            return
        notifier = self._notifier
        if notifier is None:
            return

        try:
            await notifier(message)
        except Exception:
            # 通知失败不能反过来杀死 40 分钟的地下城任务。
            pass

    def _set_pending(self, pending: _PendingDecision) -> bool:
        with self._pending_lock:
            if self._pending is not None:
                return False
            self._pending = pending

        with self._status_lock:
            self._status.pending_kind = pending.kind

        return True

    def _take_pending(self) -> _PendingDecision | None:
        with self._pending_lock:
            return self._pending

    def _clear_pending(self, pending: _PendingDecision) -> None:
        with self._pending_lock:
            if self._pending is pending:
                self._pending = None

        with self._status_lock:
            self._status.pending_kind = None

    def _release_pending(self, default_result: Any) -> None:
        pending = self._take_pending()
        if pending is None:
            return

        pending.result = default_result
        pending.event.set()
        self._clear_pending(pending)

    def _wait_password(self, username: str) -> str | None:
        """工作线程在 Cookie 失效时等待 QQ 侧提供一次密码。"""
        pending = _PendingDecision(
            kind="password",
            event=threading.Event(),
            payload={"username": username},
        )

        if not self._set_pending(pending):
            return None

        with self._status_lock:
            self._status.phase = "waiting_password"
            self._status.pending_kind = "password"

        self._notify_from_thread(
            "Aether 登录状态已失效\n"
            f"账号：{username}\n"
            "请最好【私聊 Bot】发送：\n"
            "/aether 密码 <你的 Aether 密码>\n\n"
            "密码只用于本次重新登录，不会写入配置或输出到日志。"
        )

        pending.event.wait()

        password = pending.result
        # 尽快从 pending 对象里移除引用。
        pending.result = None
        self._clear_pending(pending)

        if isinstance(password, str) and password:
            with self._status_lock:
                self._status.phase = "starting"
            return password

        return None

    def _wait_layout_decision(
        self,
        candidate: LayoutCandidate,
    ) -> Literal["accept", "refresh", "abort"]:
        pending = _PendingDecision(
            kind="layout",
            event=threading.Event(),
            payload=candidate,
        )

        if not self._set_pending(pending):
            return "abort"

        counts_text = "，".join(
            f"{node_type}={count}"
            for node_type, count in candidate.counts.items()
        )
        layout_text = " | ".join(candidate.layout)

        self._notify_from_thread(
            "Aether 布局候选\n"
            f"第 {candidate.attempt} 张\n"
            f"评分：{candidate.score:g}\n"
            f"{counts_text}\n"
            f"{layout_text}\n\n"
            "发送：/aether 接受、/aether 刷新 或 /aether 终止"
        )

        pending.event.wait()

        result = pending.result
        self._clear_pending(pending)

        if result in {"accept", "refresh", "abort"}:
            return result
        return "abort"

    def _wait_event_decision(self, info: UnknownEvent) -> int | None:
        pending = _PendingDecision(
            kind="event",
            event=threading.Event(),
            payload=info,
        )

        if not self._set_pending(pending):
            return None

        lines = [
            "Aether 遇到未知事件",
            f"{info.event_name} [{info.event_id}]",
        ]

        if info.options:
            lines.append("可选项：")
            for index, name in enumerate(info.options):
                lines.append(f"{index}. {name}")
        else:
            lines.append("前端返回中没有解析出选项名称，请按页面对应下标选择。")

        lines.append("")
        lines.append("发送：/aether 事件 <下标>")

        self._notify_from_thread("\n".join(lines))

        pending.event.wait()

        result = pending.result
        self._clear_pending(pending)

        if isinstance(result, int) and result >= 0:
            return result
        return None

    def submit_layout(
        self,
        decision: Literal["accept", "refresh", "abort"],
    ) -> tuple[bool, str]:
        pending = self._take_pending()

        if pending is None or pending.kind != "layout":
            return False, "当前没有等待处理的布局候选。"

        pending.result = decision
        pending.event.set()

        text = {
            "accept": "已接受当前布局。",
            "refresh": "已要求刷新布局。",
            "abort": "已终止当前地下城任务。",
        }[decision]
        return True, text

    def submit_event(self, choice_index: int) -> tuple[bool, str]:
        pending = self._take_pending()

        if pending is None or pending.kind != "event":
            return False, "当前没有等待处理的未知事件。"

        if choice_index < 0:
            return False, "事件选项下标不能小于 0。"

        info = pending.payload
        if isinstance(info, UnknownEvent) and info.options:
            if choice_index >= len(info.options):
                return False, f"事件只有 {len(info.options)} 个已知选项。"

        pending.result = choice_index
        pending.event.set()
        return True, f"已选择事件选项 {choice_index}。"

    def submit_password(self, password: str) -> tuple[bool, str]:
        pending = self._take_pending()

        if pending is None or pending.kind != "password":
            return False, "当前没有等待输入密码的 Aether 登录。"

        if not password:
            return False, "密码不能为空。"

        pending.result = password
        pending.event.set()

        # 不复述、不记录密码。
        return True, "密码已接收，正在继续登录。"

    def request_stop(self) -> tuple[bool, str]:
        if self.scheduler.running:
            return self.scheduler.request_stop()

        if not self.single_running:
            return False, "当前没有运行中的 Aether 任务。"

        self._stop_requested.set()

        pending = self._take_pending()
        if pending is not None:
            if pending.kind == "layout":
                pending.result = "abort"
            else:
                pending.result = None
            pending.event.set()

        return True, "已请求停止；会在安全节点暂停并保留地下城进度。"

    def status_payload(self)->dict[str,Any]:
        batch=None
        if self.scheduler.running or not self.single_running and self.scheduler.has_status:
            batch=self.scheduler.status_payload()
        if batch is not None:
            return {
                "version":1,
                "mode":"batch",
                "running":batch["running"],
                "recoverable":batch["recoverable"],
                "updated_at":time.time(),
                "single":None,
                "batch":batch,
            }
        with self._status_lock:
            status=ManagerStatus(**self._status.__dict__)
        if not status.running and status.phase=="idle":
            return {
                "version":1,
                "mode":"idle",
                "running":False,
                "recoverable":False,
                "updated_at":time.time(),
                "single":None,
                "batch":None,
            }
        return {
            "version":1,
            "mode":"single",
            "running":status.running,
            "recoverable":False,
            "updated_at":time.time(),
            "single":{
                "preset_key":status.preset_key,
                "preset_label":status.preset_label,
                "fast_mode":status.fast_mode,
                "phase":status.phase,
                "node_name":status.node_name,
                "node_index":status.node_index,
                "nodes":list(status.nodes),
                "started_at":status.started_at,
                "last_message":status.last_message,
                "pending_kind":status.pending_kind,
            },
            "batch":None,
        }

    def status_text(self) -> str:
        if self.scheduler.running:
            return self.scheduler.status_text()

        if not self.single_running and self.scheduler.has_status:
            return self.scheduler.status_text()

        with self._status_lock:
            status = ManagerStatus(**self._status.__dict__)

        if not status.running and status.phase == "idle":
            return "Aether：当前空闲。"

        lines = [
            f"Aether：{'运行中' if status.running else '未运行'}",
        ]

        if status.preset_label:
            lines.append(f"副本：{status.preset_label}")
        lines.append(
            f"模式：{'快速' if status.fast_mode else '普通'}"
        )
        if status.phase:
            lines.append(f"状态：{status.phase}")
        if status.node_name:
            node = status.node_name
            if status.node_index is not None:
                node += f"（节点 {status.node_index}）"
            lines.append(f"当前：{node}")

        if status.started_at:
            elapsed = max(0, int(time.time() - status.started_at))
            minutes, seconds = divmod(elapsed, 60)
            lines.append(f"运行：{minutes}分{seconds:02d}秒")

        if status.pending_kind == "layout":
            lines.append("等待：布局选择")
        elif status.pending_kind == "event":
            lines.append("等待：未知事件选择")
        elif status.pending_kind == "password":
            lines.append("等待：Aether 登录密码")

        if status.last_message:
            lines.append(f"最近：{status.last_message}")

        return "\n".join(lines)


aether_manager = AetherManager()
