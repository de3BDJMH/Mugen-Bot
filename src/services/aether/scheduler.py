from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from . import config as cfg
from .core import (
    AetherClient,
    AccelerationMode,
    DUNGEON_PRESETS,
    DungeonPreset,
    ResumeMatch,
    RuntimeHooks,
    detect_resume_match,
    initialize_client_pool,
    normalize_runtime_nodes,
    run_preset,
)
from .runtime_settings import load_runtime_settings
from .task_plans import load_task_plans_config
from src.storage.aether import AetherConfigError

Notifier = Callable[[str], Awaitable[None]]

TaskStatus = Literal[
    "pending",
    "running",
    "success",
    "failed",
    "blocked",
    "uncertain",
    "skipped",
    "cancelled",
]
TaskAccelerationPolicy = Literal["never", "auto", "always"]
PlanRunMode = Literal["save", "balanced", "rush"]

RUN_MODE_LABELS: dict[PlanRunMode, str] = {
    "save": "省票",
    "balanced": "平衡",
    "rush": "赶时间",
}

RUN_MODE_ALIASES: dict[str, PlanRunMode] = {
    "save": "save",
    "省票": "save",
    "省": "save",
    "节省": "save",
    "balanced": "balanced",
    "balance": "balanced",
    "平衡": "balanced",
    "rush": "rush",
    "fast": "rush",
    "赶时间": "rush",
    "赶": "rush",
}

ACCEL_POLICY_ALIASES: dict[str, TaskAccelerationPolicy] = {
    "never": "never",
    "no": "never",
    "off": "never",
    "不用": "never",
    "不加速": "never",
    "auto": "auto",
    "自动": "auto",
    "always": "always",
    "yes": "always",
    "on": "always",
    "总是": "always",
    "强制": "always",
}

CHECKPOINT_VERSION = 1
RESOURCE_REFRESH_INTERVAL = 0.25
VALID_TASK_STATUSES: set[str] = {
    "pending",
    "running",
    "success",
    "failed",
    "blocked",
    "uncertain",
    "skipped",
    "cancelled",
}


def _preset_signature(preset: DungeonPreset) -> str:
    """保存足够的信息，避免重启后 config 已改变却继续跑旧任务。"""
    payload = {
        "key": preset.key,
        "preset_id": preset.preset_id,
        "difficulty": preset.difficulty,
        "visibility": preset.visibility,
        "layout_rule": preset.layout_rule,
        "opener": preset.opener.username,
        "captain": preset.leader.username,
        "party": [
            {
                "username": member.username,
                "kind": member.kind,
                "preset_index": member.preset_index,
                "leave_after_enter":member.leave_after_enter,
            }
            for member in preset.party
        ],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True)
class TaskPlanItem:
    preset_key: str
    count: int = 1
    acceleration: TaskAccelerationPolicy = "auto"

    # 批量清本默认不在营地等待。
    # 某个高难本确实需要营地回血时可单项设为 False。
    skip_camp_wait: bool = True


@dataclass(frozen=True)
class TaskPlan:
    key: str
    name: str
    items: tuple[TaskPlanItem, ...]

    @property
    def total(self) -> int:
        return sum(item.count for item in self.items)


@dataclass
class DungeonTask:
    sequence: int
    preset_key: str
    acceleration: TaskAccelerationPolicy = "auto"
    skip_camp_wait: bool = True
    status: TaskStatus = "pending"
    phase: str = "pending"
    node_name: str | None = None
    node_index: int | None = None
    nodes: tuple[dict[str, Any], ...] = ()
    dungeon_id:str|None=None
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None

    # 快照用于重启恢复时判断“原任务到底占用了哪些自有角色”，
    # 即使配置文件后来改了也不会丢掉资源信息。
    owned_snapshot: tuple[str, ...] = ()
    runtime_owned_snapshot:tuple[str,...]=()
    preset_signature: str = ""
    runtime_party_ready:bool=False

    # 某些失败/不确定状态必须继续锁住这些 owned 角色，
    # 防止后面的任务在活动地下城上继续撞。
    holds_resource_lock: bool = False
    lock_reason: str | None = None

    @property
    def preset(self) -> DungeonPreset:
        return DUNGEON_PRESETS[self.preset_key]

    @property
    def preset_label(self) -> str:
        preset = DUNGEON_PRESETS.get(self.preset_key)
        return preset.label if preset is not None else self.preset_key

    @property
    def owned_usernames(self) -> tuple[str, ...]:
        if self.owned_snapshot:
            return self.owned_snapshot

        preset = DUNGEON_PRESETS.get(self.preset_key)
        if preset is None:
            return ()
        return tuple(preset.owned_usernames)

    @property
    def owned_characters(self) -> frozenset[str]:
        return frozenset(self.owned_usernames)

    @property
    def runtime_owned_usernames(self)->tuple[str,...]:
        if self.runtime_owned_snapshot:
            return self.runtime_owned_snapshot
        preset=DUNGEON_PRESETS.get(self.preset_key)
        if preset is None:
            return ()
        return tuple(preset.runtime_owned_usernames)

    @property
    def runtime_owned_characters(self)->frozenset[str]:
        return frozenset(self.runtime_owned_usernames)

    @property
    def active_owned_characters(self)->frozenset[str]:
        if self.runtime_party_ready:
            return self.runtime_owned_characters
        return self.owned_characters

    def to_json(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "preset_key": self.preset_key,
            "acceleration": self.acceleration,
            "skip_camp_wait": self.skip_camp_wait,
            "status": self.status,
            "phase": self.phase,
            "node_name": self.node_name,
            "node_index": self.node_index,
            "nodes": list(self.nodes),
            "dungeon_id":self.dungeon_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "owned_snapshot": list(self.owned_snapshot),
            "runtime_owned_snapshot":list(self.runtime_owned_snapshot),
            "preset_signature": self.preset_signature,
            "runtime_party_ready":self.runtime_party_ready,
            "holds_resource_lock": self.holds_resource_lock,
            "lock_reason": self.lock_reason,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "DungeonTask":
        status = str(raw.get("status", "pending"))
        if status not in VALID_TASK_STATUSES:
            status = "blocked"

        acceleration_raw = str(raw.get("acceleration", "auto")).lower()
        acceleration: TaskAccelerationPolicy
        if acceleration_raw in {"never", "auto", "always"}:
            acceleration = acceleration_raw  # type: ignore[assignment]
        else:
            acceleration = "auto"

        raw_snapshot = raw.get("owned_snapshot")
        if isinstance(raw_snapshot, list):
            owned_snapshot = tuple(
                str(value)
                for value in raw_snapshot
                if isinstance(value, str) and value
            )
        else:
            owned_snapshot = ()
        raw_runtime_snapshot=raw.get("runtime_owned_snapshot")
        if isinstance(raw_runtime_snapshot,list):
            runtime_owned_snapshot=tuple(
                str(value)
                for value in raw_runtime_snapshot
                if isinstance(value,str) and value
            )
        else:
            runtime_owned_snapshot=()

        node_index_raw = raw.get("node_index")
        try:
            node_index = (
                None
                if node_index_raw is None
                else int(node_index_raw)
            )
        except (TypeError, ValueError):
            node_index = None

        return cls(
            sequence=int(raw["sequence"]),
            preset_key=str(raw["preset_key"]),
            acceleration=acceleration,
            skip_camp_wait=bool(raw.get("skip_camp_wait", True)),
            status=status,  # type: ignore[arg-type]
            phase=str(raw.get("phase", status)),
            node_name=(
                str(raw["node_name"])
                if raw.get("node_name") is not None
                else None
            ),
            node_index=node_index,
            nodes=normalize_runtime_nodes(raw.get("nodes")),
            dungeon_id=(
                str(raw["dungeon_id"])
                if raw.get("dungeon_id")
                else None
            ),
            started_at=(
                float(raw["started_at"])
                if raw.get("started_at") is not None
                else None
            ),
            finished_at=(
                float(raw["finished_at"])
                if raw.get("finished_at") is not None
                else None
            ),
            error=(
                str(raw["error"])
                if raw.get("error") is not None
                else None
            ),
            owned_snapshot=owned_snapshot,
            runtime_owned_snapshot=runtime_owned_snapshot,
            preset_signature=str(raw.get("preset_signature", "")),
            runtime_party_ready=bool(raw.get("runtime_party_ready",False)),
            holds_resource_lock=bool(
                raw.get("holds_resource_lock", False)
            ),
            lock_reason=(
                str(raw["lock_reason"])
                if raw.get("lock_reason") is not None
                else None
            ),
        )


def resolve_run_mode(value: str | None) -> PlanRunMode | None:
    if value is None:
        return None
    return RUN_MODE_ALIASES.get(str(value).strip().lower())


def _parse_acceleration_policy(
    value: object,
    *,
    context: str,
) -> TaskAccelerationPolicy:
    # v15 兼容：原来的 fast=True/False -> always/never。
    if isinstance(value, bool):
        return "always" if value else "never"

    key = str(value).strip().lower()
    policy = ACCEL_POLICY_ALIASES.get(key)
    if policy is None:
        raise ValueError(
            f"{context} 的 acceleration 无效：{value!r}；"
            "可选 never / auto / always"
        )
    return policy


def _parse_plan_item(raw: object, *, context: str) -> TaskPlanItem:
    if isinstance(raw, str):
        preset_key = raw
        count = 1
        acceleration: TaskAccelerationPolicy = "auto"
        skip_camp_wait = True

    elif isinstance(raw, dict):
        preset_key = str(
            raw.get("preset")
            or raw.get("preset_key")
            or ""
        )
        if not preset_key:
            raise ValueError(f"{context} 缺少 preset")

        count = int(raw.get("count", 1))

        if "acceleration" in raw:
            acceleration = _parse_acceleration_policy(
                raw["acceleration"],
                context=context,
            )
        elif "fast" in raw or "fast_mode" in raw:
            acceleration = _parse_acceleration_policy(
                raw.get("fast", raw.get("fast_mode")),
                context=context,
            )
        else:
            acceleration = "auto"

        skip_camp_wait = bool(raw.get("skip_camp_wait", True))

    elif isinstance(raw, (list, tuple)):
        if len(raw) == 2:
            preset_key = str(raw[0])
            count = int(raw[1])
            acceleration = "auto"
            skip_camp_wait = True

        elif len(raw) == 3:
            preset_key = str(raw[0])
            count = int(raw[1])
            acceleration = _parse_acceleration_policy(
                raw[2],
                context=context,
            )
            skip_camp_wait = True

        elif len(raw) == 4:
            preset_key = str(raw[0])
            count = int(raw[1])
            acceleration = _parse_acceleration_policy(
                raw[2],
                context=context,
            )
            skip_camp_wait = bool(raw[3])

        else:
            raise TypeError(
                f"{context} tuple 必须是 "
                "(preset, count)、"
                "(preset, count, acceleration) 或 "
                "(preset, count, acceleration, skip_camp_wait)"
            )
    else:
        raise TypeError(f"{context} 格式无效")

    if preset_key not in DUNGEON_PRESETS:
        raise ValueError(f"{context} 引用了不存在的预设：{preset_key}")

    if count <= 0:
        raise ValueError(f"{context} 的 count 必须大于 0")

    return TaskPlanItem(
        preset_key=preset_key,
        count=count,
        acceleration=acceleration,
        skip_camp_wait=skip_camp_wait,
    )


def _load_raw_task_plans() -> dict[str, Any]:
    return load_task_plans_config()


def load_task_plans() -> dict[str, TaskPlan]:
    raw_plans = _load_raw_task_plans()
    plans: dict[str, TaskPlan] = {}

    for raw_key, raw_plan in raw_plans.items():
        key = str(raw_key)

        if isinstance(raw_plan, dict):
            name = str(raw_plan.get("name") or key)
            raw_items = raw_plan.get("tasks", raw_plan.get("items"))
        else:
            name = key
            raw_items = raw_plan

        if not isinstance(raw_items, (list, tuple)):
            raise TypeError(f"任务计划 {key!r} 的 tasks 必须是 list/tuple")

        items = tuple(
            _parse_plan_item(
                raw,
                context=f"任务计划 {key!r} 第 {index} 项",
            )
            for index, raw in enumerate(raw_items, start=1)
        )

        if not items:
            raise ValueError(f"任务计划 {key!r} 不能为空")

        plans[key] = TaskPlan(
            key=key,
            name=name,
            items=items,
        )

    return plans


def resolve_effective_acceleration(
    policy: TaskAccelerationPolicy,
    run_mode: PlanRunMode,
) -> AccelerationMode:
    """任务项策略 + 本次计划模式 -> Runner 最终战斗加速模式。"""
    if policy == "never":
        return "never"
    if policy == "always":
        return "always"

    if run_mode == "save":
        return "never"
    if run_mode == "balanced":
        return "threshold"
    return "always"


class AetherTaskScheduler:
    """批量地下城调度器 + 持久化断点恢复。

    关键恢复原则：
    - success 永远不重跑；
    - pending 继续排队；
    - 进程中断时的 running 会先查询服务器当前地下城；
      * exact match -> 自动续跑；
      * 没有当前地下城 -> uncertain，绝不擅自重打一把；
      * 有地下城但不匹配 -> blocked 并锁角色；
    - uncertain 需要用户明确 /aether 重试 <n> 或 /aether 跳过 <n>。
    """

    def __init__(self) -> None:
        self._runner: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._notifier: Notifier | None = None
        self._stop_requested = threading.Event()

        self._lock = threading.Lock()
        self._checkpoint_io_lock = threading.Lock()
        self._history_io_lock = threading.Lock()

        self._plan_key: str | None = None
        self._plan_name: str | None = None
        self._run_mode: PlanRunMode = "save"
        self._run_id: str | None = None
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._archived_at: float | None = None
        self._tasks: list[DungeonTask] = []
        self._blocked_characters: set[str] = set()
        self._failure_streaks: dict[str, int] = {}
        self._client_pool: dict[str, AetherClient] = {}
        self._last_message: str | None = None

        self._checkpoint_loaded = False
        self._checkpoint_error: str | None = None

        self._load_checkpoint()

    # ------------------------------------------------------------------
    # 基础状态 / checkpoint
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        runner = self._runner
        return bool(runner and not runner.done())

    @property
    def has_status(self) -> bool:
        with self._lock:
            return bool(self._plan_key)

    @property
    def has_unresolved_checkpoint(self) -> bool:
        with self._lock:
            return any(
                task.status in {
                    "pending",
                    "running",
                    "uncertain",
                    "blocked",
                }
                or task.holds_resource_lock
                for task in self._tasks
            )

    @property
    def checkpoint_path(self) -> Path:
        configured = getattr(cfg, "AETHER_TASK_STATE_FILE", None)
        if configured:
            return Path(str(configured))
        return Path(cfg.AETHER_DATA_DIR) / "task_state.json"

    @property
    def history_dir(self) -> Path:
        configured = getattr(cfg, "AETHER_TASK_HISTORY_DIR", None)
        if configured:
            return Path(str(configured))
        return Path(cfg.AETHER_DATA_DIR) / "task_history"

    @property
    def failure_limit(self) -> int:
        return load_runtime_settings().consecutive_failure_limit

    @staticmethod
    def _new_run_id() -> str:
        return (
            time.strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8]
        )

    def _run_result_locked(self) -> str:
        if any(
            task.status in {"pending", "running", "uncertain", "blocked"}
            or task.holds_resource_lock
            for task in self._tasks
        ):
            return "unfinished"

        if any(
            task.status in {"failed", "cancelled"}
            for task in self._tasks
        ):
            return "completed_with_failures"

        return "completed"

    def _is_terminal_locked(self) -> bool:
        return bool(self._tasks) and self._run_result_locked() != "unfinished"

    def _checkpoint_payload_locked(self) -> dict[str, Any]:
        return {
            "version": CHECKPOINT_VERSION,
            "saved_at": time.time(),
            "run_id": self._run_id,
            "plan_key": self._plan_key,
            "plan_name": self._plan_name,
            "run_mode": self._run_mode,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "archived_at": self._archived_at,
            "result": self._run_result_locked(),
            "last_message": self._last_message,
            "blocked_characters": sorted(self._blocked_characters),
            "failure_streaks": dict(self._failure_streaks),
            "tasks": [task.to_json() for task in self._tasks],
        }

    def _persist_checkpoint(self) -> None:
        """原子保存。

        顺序固定为 io_lock -> state_lock，且其他地方不会反向持锁调用，
        避免并行任务同时写 checkpoint 时产生旧快照覆盖新快照。
        """
        with self._checkpoint_io_lock:
            with self._lock:
                if not self._plan_key:
                    return
                payload = self._checkpoint_payload_locked()

            path = self.checkpoint_path
            tmp = path.with_name(path.name + ".tmp")

            try:
                path.parent.mkdir(parents=True, exist_ok=True)

                with tmp.open("w", encoding="utf-8") as file:
                    json.dump(
                        payload,
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )
                    file.flush()
                    os.fsync(file.fileno())

                os.replace(tmp, path)

            except OSError as exc:
                print(f"Aether 任务 checkpoint 保存失败：{exc}")
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass

    def _archive_current_run_if_terminal(
        self,
        *,
        include_failures: bool = False,
    ) -> Path | None:
        """把已经结束的一轮保存到 task_history。

        正常全部完成时立即归档。
        如果存在普通 failed，则先保留当前 checkpoint，方便用户继续重试；
        只有下一轮新任务要覆盖它时才把这份失败结果归档。
        """
        with self._history_io_lock:
            with self._lock:
                if not self._plan_key or not self._is_terminal_locked():
                    return None
                if self._archived_at is not None:
                    return None

                result = self._run_result_locked()
                if result == "completed_with_failures" and not include_failures:
                    return None

                if self._run_id is None:
                    self._run_id = self._new_run_id()
                if self._finished_at is None:
                    self._finished_at = time.time()

                archive_time = time.time()
                payload = self._checkpoint_payload_locked()
                payload["archived_at"] = archive_time
                run_id = self._run_id
                plan_key = self._plan_key or "unknown"

            safe_plan = "".join(
                char if char.isalnum() or char in {"-", "_"} else "_"
                for char in plan_key
            )
            path = self.history_dir / f"{run_id}_{safe_plan}.json"
            tmp = path.with_name(path.name + ".tmp")

            try:
                path.parent.mkdir(parents=True, exist_ok=True)

                with tmp.open("w", encoding="utf-8") as file:
                    json.dump(
                        payload,
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )
                    file.flush()
                    os.fsync(file.fileno())

                os.replace(tmp, path)

                with self._lock:
                    self._archived_at = archive_time

                self._persist_checkpoint()
                return path

            except OSError as exc:
                print(f"Aether 任务历史归档失败：{exc}")
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
                return None

    def _load_checkpoint(self) -> None:
        path = self.checkpoint_path
        if not path.exists():
            return

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._checkpoint_error = f"读取 checkpoint 失败：{exc}"
            print(f"Aether {self._checkpoint_error}")
            return

        if not isinstance(payload, dict):
            self._checkpoint_error = "checkpoint 顶层不是 object"
            print(f"Aether {self._checkpoint_error}")
            return

        try:
            version = int(payload.get("version", 0))
        except (TypeError, ValueError):
            version = 0

        if version != CHECKPOINT_VERSION:
            self._checkpoint_error = (
                f"checkpoint 版本不支持：{version}"
            )
            print(f"Aether {self._checkpoint_error}")
            return

        raw_tasks = payload.get("tasks")
        if not isinstance(raw_tasks, list):
            self._checkpoint_error = "checkpoint 缺少 tasks"
            print(f"Aether {self._checkpoint_error}")
            return

        try:
            tasks = [
                DungeonTask.from_json(raw)
                for raw in raw_tasks
                if isinstance(raw, dict)
            ]
        except (KeyError, TypeError, ValueError) as exc:
            self._checkpoint_error = f"checkpoint 任务解析失败：{exc}"
            print(f"Aether {self._checkpoint_error}")
            return

        run_mode_raw = str(payload.get("run_mode", "save"))
        run_mode = resolve_run_mode(run_mode_raw) or "save"

        with self._lock:
            self._run_id = (
                str(payload["run_id"])
                if payload.get("run_id") is not None
                else self._new_run_id()
            )
            self._plan_key = (
                str(payload["plan_key"])
                if payload.get("plan_key") is not None
                else None
            )
            self._plan_name = (
                str(payload["plan_name"])
                if payload.get("plan_name") is not None
                else self._plan_key
            )
            self._run_mode = run_mode
            self._started_at = (
                float(payload["started_at"])
                if payload.get("started_at") is not None
                else None
            )
            self._finished_at = (
                float(payload["finished_at"])
                if payload.get("finished_at") is not None
                else None
            )
            self._archived_at = (
                float(payload["archived_at"])
                if payload.get("archived_at") is not None
                else None
            )

            raw_streaks = payload.get("failure_streaks")
            if isinstance(raw_streaks, dict):
                self._failure_streaks = {
                    str(username): max(0, int(value))
                    for username, value in raw_streaks.items()
                    if isinstance(username, str)
                }
            else:
                self._failure_streaks = {}

            self._tasks = tasks
            self._last_message = (
                str(payload["last_message"])
                if payload.get("last_message") is not None
                else "已从磁盘读取上次任务状态"
            )
            self._checkpoint_loaded = True
            self._rebuild_blocked_characters_locked()

    def _rebuild_blocked_characters_locked(self) -> None:
        blocked: set[str] = set()
        for task in self._tasks:
            if task.holds_resource_lock:
                blocked.update(task.active_owned_characters)
        self._blocked_characters = blocked

    # ------------------------------------------------------------------
    # 任务计划配置
    # ------------------------------------------------------------------

    def plan_items(self) -> list[tuple[str, str, int]]:
        plans = load_task_plans()
        return [
            (key, plan.name, plan.total)
            for key, plan in plans.items()
        ]

    def resolve_plan(self, value: str) -> str | None:
        value = value.strip()
        plans = load_task_plans()

        if value in plans:
            return value

        items = list(plans.items())

        try:
            index = int(value)
        except ValueError:
            index = -1

        if 1 <= index <= len(items):
            return items[index - 1][0]

        for key, plan in items:
            if value == plan.name:
                return key

        return None

    def resolve_run_mode(self, value: str | None) -> PlanRunMode | None:
        return resolve_run_mode(value)

    def plan_menu(self) -> str:
        items = self.plan_items()
        if not items:
            return (
                "当前没有配置 Aether 批量任务。\n"
                "请配置 data/aether/configs/task_plans.json。"
            )

        lines = ["请选择 Aether 批量任务："]
        for index, (key, name, total) in enumerate(items, start=1):
            lines.append(f"{index}. {name} [{key}] · {total} 次")

        lines.extend([
            "",
            "运行模式：省票 / 平衡 / 赶时间",
            "省票：auto 不用券（默认）",
            "平衡：auto 仅长战斗用券",
            "赶时间：auto 每场尽量用券",
        ])

        if self.has_unresolved_checkpoint:
            lines.extend([
                "",
                "检测到上次未完成任务：",
                "先发送 /aether 状态 查看，",
                "再用 /aether 恢复 继续。",
            ])

        return "\n".join(lines)

    @staticmethod
    def _expand_plan(plan: TaskPlan) -> list[DungeonTask]:
        tasks: list[DungeonTask] = []
        sequence = 1

        for item in plan.items:
            preset = DUNGEON_PRESETS[item.preset_key]
            signature = _preset_signature(preset)
            owned = tuple(preset.owned_usernames)
            runtime_owned=tuple(preset.runtime_owned_usernames)

            for _ in range(item.count):
                tasks.append(
                    DungeonTask(
                        sequence=sequence,
                        preset_key=item.preset_key,
                        acceleration=item.acceleration,
                        skip_camp_wait=item.skip_camp_wait,
                        owned_snapshot=owned,
                        runtime_owned_snapshot=runtime_owned,
                        preset_signature=signature,
                    )
                )
                sequence += 1

        return tasks

    # ------------------------------------------------------------------
    # 启动 / 恢复
    # ------------------------------------------------------------------

    async def start(
        self,
        plan_key: str,
        notifier: Notifier,
        *,
        run_mode: PlanRunMode = "save",
    ) -> tuple[bool, str]:
        if self.running:
            return False, "已有 Aether 批量任务正在运行。"

        if self.has_unresolved_checkpoint:
            return (
                False,
                "检测到上一份批量任务尚未处理完。\n"
                "请先发送 /aether 状态 查看，"
                "再使用 /aether 恢复；"
                "不确定项可用 /aether 重试 <编号> 或 /aether 跳过 <编号>。",
            )

        # 上一轮已经结束但还没来得及归档时，在覆盖 task_state.json 前补归档。
        if self.has_status:
            self._archive_current_run_if_terminal(include_failures=True)

        if run_mode not in {"save", "balanced", "rush"}:
            return False, f"未知任务运行模式：{run_mode}"

        try:
            from .core import reload_dungeon_presets

            reload_dungeon_presets()
            plans=load_task_plans()
        except (AetherConfigError,KeyError,TypeError,ValueError) as exc:
            return False,f"Aether 批量任务配置无效：{exc}"
        plan = plans.get(plan_key)
        if plan is None:
            return False, f"不存在 Aether 任务计划：{plan_key}"

        self._loop = asyncio.get_running_loop()
        self._notifier = notifier
        self._stop_requested.clear()
        self._notification_seen=set()

        with self._lock:
            self._plan_key = plan.key
            self._plan_name = plan.name
            self._run_mode = run_mode
            self._run_id = self._new_run_id()
            self._started_at = time.time()
            self._finished_at = None
            self._archived_at = None
            self._tasks = self._expand_plan(plan)
            self._blocked_characters.clear()
            self._failure_streaks.clear()
            self._client_pool = {}
            self._last_message = "正在初始化 OAuth 角色池"
            self._checkpoint_loaded = False

        # 在真正启动第一个子任务前先落盘。
        self._persist_checkpoint()

        self._runner = asyncio.create_task(
            self._run_current_plan(recovering=False),
            name=f"aether-plan:{plan.key}",
        )

        return (
            True,
            f"已启动批量任务：{plan.name}（{plan.total} 次）"
            f" · {RUN_MODE_LABELS[run_mode]}模式",
        )

    async def recover(
        self,
        notifier: Notifier,
    ) -> tuple[bool, str]:
        if self.running:
            return False, "已有 Aether 批量任务正在运行。"

        if not self.has_status:
            return False, "没有找到可恢复的 Aether 批量任务 checkpoint。"

        with self._lock:
            self._promote_exact_resume_candidates_locked()
            running_count = sum(
                task.status == "running"
                for task in self._tasks
            )
            pending_count = sum(
                task.status == "pending"
                for task in self._tasks
            )
            uncertain_count = sum(
                task.status == "uncertain"
                for task in self._tasks
            )
            blocked_lock_count = sum(
                task.status == "blocked" and task.holds_resource_lock
                for task in self._tasks
            )
            plan_name = self._plan_name or self._plan_key or "未知任务"

        if running_count == 0 and pending_count == 0:
            if uncertain_count or blocked_lock_count:
                return (
                    False,
                    "当前没有可以安全自动继续的任务。\n"
                    "请先查看 /aether 状态，"
                    "对不确定/阻塞项使用：\n"
                    "/aether 重试 <编号>\n"
                    "/aether 跳过 <编号>",
                )
            return False, "这份批量任务已经没有待恢复项。"

        self._loop = asyncio.get_running_loop()
        self._notifier = notifier
        self._stop_requested.clear()

        with self._lock:
            self._last_message = "正在恢复 checkpoint 并重新检查中断任务"
            self._notification_seen=set()

        self._persist_checkpoint()

        self._runner = asyncio.create_task(
            self._run_current_plan(recovering=True),
            name=f"aether-recover:{self._plan_key or 'unknown'}",
        )

        return (
            True,
            f"开始恢复：{plan_name}\n"
            f"中断时运行 {running_count}，等待 {pending_count}。"
        )

    def _promote_exact_resume_candidates_locked(self)->None:
        """将带准确地下城 ID 的活动失败项重新交给恢复检查。"""
        changed=False
        for task in self._tasks:
            if (
                task.status not in {"failed","blocked"}
                or task.lock_reason not in {"active_dungeon","paused_active"}
                or not task.dungeon_id
            ):
                continue
            task.status="running"
            task.phase="recheck_required"
            task.error=None
            task.holds_resource_lock=False
            task.lock_reason=None
            self._reset_failure_streaks_locked(task)
            changed=True
        if changed:
            self._rebuild_blocked_characters_locked()

    async def _run_current_plan(self, *, recovering: bool) -> None:
        with self._lock:
            plan_name = self._plan_name or self._plan_key or "未知任务"

        try:
            pool = await asyncio.to_thread(initialize_client_pool)
            if pool is None:
                self._set_last_message("OAuth 角色池初始化失败")
                await self._safe_notify(
                    f"Aether 批量任务「{plan_name}」启动失败："
                    "OAuth 角色池初始化失败。"
                )
                return

            with self._lock:
                self._client_pool = pool
                self._last_message = (
                    "角色池已加载："
                    + "，".join(pool)
                )
            self._persist_checkpoint()

            validation_events = self._validate_task_definitions(pool)
            for event_type, task in validation_events:
                await self._notify_task_event(event_type, task)

            if recovering:
                recovery_events = await asyncio.to_thread(
                    self._prepare_interrupted_tasks,
                    pool,
                )
                for event_type, task in recovery_events:
                    await self._notify_task_event(event_type, task)

            running: dict[
                asyncio.Task[tuple[DungeonTask, bool, set[str]]],
                DungeonTask,
            ] = {}

            while True:
                # “停止”在批量模式里是可恢复暂停：
                # 不再启动新任务，但保留所有 pending 给下次 /aether 恢复。
                if self._stop_requested.is_set():
                    launched = False
                else:
                    launched = self._launch_available_tasks(running)

                pending_exists = self._has_status("pending")

                if not running:
                    if self._stop_requested.is_set():
                        self._set_last_message(
                            "批量任务已暂停；pending 已保留，"
                            "可稍后 /aether 恢复"
                        )
                        break

                    if not pending_exists:
                        break

                    if not launched:
                        # 剩余 pending 全被 holds_resource_lock 挡住时，
                        # 不把它们永久改成 blocked；保留 pending，
                        # 等用户解决不确定项后再次 /aether 恢复。
                        if self._pending_all_waiting_for_locks():
                            self._set_last_message(
                                "剩余任务正在等待被锁角色；"
                                "请处理不确定/活动地下城后再次恢复"
                            )
                            break

                if running:
                    done, _ = await asyncio.wait(
                        tuple(running),
                        timeout=RESOURCE_REFRESH_INTERVAL,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for future in done:
                        task = running.pop(future)

                        try:
                            _, ok, blocked = future.result()

                        except Exception as exc:
                            task.holds_resource_lock = True
                            task.lock_reason = "worker_exception"
                            self._finish_task(
                                task,
                                success=False,
                                error=f"{type(exc).__name__}: {exc}",
                            )
                            self._rebuild_blocked_characters()
                            await self._notify_task_event("failed", task)
                            continue

                        if ok:
                            self._finish_task(task, success=True)
                            await self._notify_task_event("success", task)

                        elif self._stop_requested.is_set():
                            # Core 会在安全节点返回 False，并尽量保留 exploring。
                            # 若服务器仍有活动地下城，就把它继续记为 running/paused，
                            # 下次 /恢复 会先检查再续跑。
                            if blocked:
                                with self._lock:
                                    task.status = "running"
                                    task.phase = "paused"
                                    task.error = "用户暂停；服务器仍保留当前地下城"
                                    task.holds_resource_lock = True
                                    task.lock_reason = "paused_active"
                                    task.finished_at = None
                                    self._rebuild_blocked_characters_locked()
                                self._persist_checkpoint()
                            else:
                                # 极小窗口：停止后服务器已无当前地下城。
                                # 不猜它到底完成了还是没开始，按 uncertain 处理。
                                with self._lock:
                                    task.status = "uncertain"
                                    task.phase = "uncertain"
                                    task.error = (
                                        "用户暂停后服务器已无当前地下城；"
                                        "无法确认该任务是否已结算"
                                    )
                                    task.holds_resource_lock = True
                                    task.lock_reason = "uncertain_completion"
                                    task.finished_at = None
                                    self._rebuild_blocked_characters_locked()
                                self._persist_checkpoint()

                        else:
                            if blocked:
                                task.holds_resource_lock = True
                                task.lock_reason = "active_dungeon"
                            self._finish_task(
                                task,
                                success=False,
                                error=task.error or "地下城任务失败",
                            )
                            self._rebuild_blocked_characters()
                            await self._notify_task_event("failed", task)

                elif not launched:
                    await asyncio.sleep(0.05)

        finally:
            with self._lock:
                uncertain = sum(
                    task.status == "uncertain"
                    for task in self._tasks
                )
                pending = sum(
                    task.status == "pending"
                    for task in self._tasks
                )
                interrupted_running = sum(
                    task.status == "running"
                    for task in self._tasks
                )

            if self._stop_requested.is_set():
                self._set_last_message(
                    "批量任务已按要求暂停；"
                    "running/pending checkpoint 已保留"
                )
            elif uncertain or pending or interrupted_running or any(task.holds_resource_lock for task in self._tasks):
                self._set_last_message(
                    "本轮调度已暂停，仍有未确定/等待任务"
                )
            else:
                self._set_last_message("批量任务结束")

            with self._lock:
                if self._is_terminal_locked() and self._finished_at is None:
                    self._finished_at = time.time()

            self._persist_checkpoint()
            self._archive_current_run_if_terminal()

            with self._lock:
                success=sum(task.status=="success" for task in self._tasks)
                failed=sum(task.status in {"failed","blocked","uncertain"} for task in self._tasks)
                elapsed=int(time.time()-(self._started_at or time.time()))
                unresolved=[task for task in self._tasks if task.holds_resource_lock]
                summary=f"{self._plan_name}：成功 {success}，异常 {failed}，等待 {pending}，距首次启动 {elapsed//60} 分钟（含暂停）。详情见 Web 运行状态。"
                if unresolved:
                    summary+="\n仍未解除的任务："+ "；".join(f"#{task.sequence}：{task.error or task.lock_reason}" for task in unresolved)
                title="Aether 批量任务仍有待处理项" if unresolved or pending or interrupted_running else "Aether 批量任务本轮结束"
            await self._safe_notify(
                title+"\n"+summary,kind="summary"
            )

    # ------------------------------------------------------------------
    # 恢复时的“中断 running”判定
    # ------------------------------------------------------------------

    def _prepare_interrupted_tasks(
        self,
        pool: dict[str, AetherClient],
    ) -> list[tuple[str, DungeonTask]]:
        events: list[tuple[str, DungeonTask]] = []

        with self._lock:
            interrupted = [
                task
                for task in self._tasks
                if task.status == "running"
            ]

        for task in interrupted:
            clients = [
                pool[username]
                for username in task.active_owned_characters
                if username in pool
            ]

            if len(clients) != len(task.active_owned_characters):
                with self._lock:
                    task.status = "blocked"
                    task.phase = "blocked"
                    task.error = "恢复失败：缺少部分自有角色 Client"
                    task.holds_resource_lock = False
                    task.lock_reason = None
                self._persist_checkpoint()
                events.append(("blocked", DungeonTask(**task.__dict__)))
                continue

            match=detect_resume_match(
                clients,
                DUNGEON_PRESETS,
                expected_preset_key=task.preset_key,
                expected_dungeon_id=task.dungeon_id,
                allow_legacy_adopt=task.dungeon_id is None,
            )

            if (
                isinstance(match, ResumeMatch)
                and match.preset_key == task.preset_key
            ):
                # run_preset 自己会再次 detect_resume_match 并进入 resume=True。
                with self._lock:
                    task.status = "pending"
                    task.phase = "resume_ready"
                    task.dungeon_id=match.dungeon_id
                    task.error = None
                    task.holds_resource_lock = False
                    task.lock_reason = None
                print(
                    f"恢复检查 #{task.sequence}："
                    f"服务器仍有匹配地下城，准备续跑"
                )
                events.append(("resume_ready", DungeonTask(**task.__dict__)))

            elif match is None:
                # 最危险的窗口：
                # 服务器可能已经结算成功，但 Python 还没来得及写 success；
                # 也可能根本没真正创建地下城。
                # 所以绝不自动重打一把。
                with self._lock:
                    task.status = "uncertain"
                    task.phase = "uncertain"
                    task.error = (
                        "进程中断时本任务处于 running，"
                        "但服务器现在没有未结束地下城；"
                        f"无法确认结算结果。若确认已经结束，请发送 /aether 跳过 {task.sequence}；不会自动重打"
                    )
                    task.holds_resource_lock = True
                    task.lock_reason = "uncertain_completion"
                print(
                    f"恢复检查 #{task.sequence}："
                    "服务器无当前地下城，标记 uncertain"
                )
                events.append(("uncertain", DungeonTask(**task.__dict__)))

            else:
                with self._lock:
                    task.status = "blocked"
                    task.phase = "blocked"
                    task.error = match.error or (
                        "恢复时检测到活动地下城，"
                        "但它与本任务预设不匹配；需要人工处理"
                    )
                    task.holds_resource_lock = True
                    task.lock_reason = "active_dungeon"
                print(
                    f"恢复检查 #{task.sequence}："
                    "存在不匹配的活动地下城，已阻塞"
                )
                events.append(("blocked", DungeonTask(**task.__dict__)))

            self._rebuild_blocked_characters()
            self._persist_checkpoint()

        return events

    # ------------------------------------------------------------------
    # 调度
    # ------------------------------------------------------------------

    def _validate_task_definitions(
        self,
        pool: dict[str, AetherClient],
    ) -> list[tuple[str, DungeonTask]]:
        changed = False
        events: list[tuple[str, DungeonTask]] = []

        with self._lock:
            for task in self._tasks:
                if task.status not in {"pending", "running"}:
                    continue

                preset = DUNGEON_PRESETS.get(task.preset_key)
                if preset is None:
                    task.status = "blocked"
                    task.phase = "blocked"
                    task.error = (
                        f"当前配置中已不存在预设：{task.preset_key}"
                    )
                    task.holds_resource_lock = False
                    task.lock_reason = None
                    changed = True
                    events.append(("blocked", DungeonTask(**task.__dict__)))
                    continue

                if (
                    task.preset_signature
                    and task.preset_signature != _preset_signature(preset)
                ):
                    task.status = "blocked"
                    task.phase = "blocked"
                    task.error = (
                        "checkpoint 创建后该 DungeonPreset 配置发生变化；"
                        "为避免用新配置误续旧任务，已阻塞"
                    )
                    task.holds_resource_lock = False
                    task.lock_reason = None
                    changed = True
                    events.append(("blocked", DungeonTask(**task.__dict__)))
                    continue

                missing = set(task.owned_usernames) - set(pool)
                if missing:
                    task.status = "blocked"
                    task.phase = "blocked"
                    task.error = (
                        "当前 OAuth 角色池缺少："
                        + "，".join(sorted(missing))
                    )
                    task.holds_resource_lock = False
                    task.lock_reason = None
                    changed = True
                    events.append(("blocked", DungeonTask(**task.__dict__)))

        if changed:
            self._persist_checkpoint()

        return events

    def _busy_characters(
        self,
        running: dict[asyncio.Task[Any], DungeonTask],
    ) -> set[str]:
        busy: set[str] = set()
        for task in running.values():
            busy.update(task.active_owned_characters)
        return busy

    def _launch_available_tasks(
        self,
        running: dict[
            asyncio.Task[tuple[DungeonTask, bool, set[str]]],
            DungeonTask,
        ],
    ) -> bool:
        launched = False
        busy = self._busy_characters(running)

        with self._lock:
            snapshot = list(self._tasks)
            blocked = set(self._blocked_characters)

        earlier_pending: list[DungeonTask] = []

        for task in snapshot:
            if task.status != "pending":
                continue

            mine=set(task.active_owned_characters)

            if mine & blocked:
                earlier_pending.append(task)
                continue

            if mine & busy:
                earlier_pending.append(task)
                continue

            # 同一个最终推进角色自己的任务不能被后项插队。
            # 只负责开本并退出的角色允许被后面的独立队伍复用。
            if any(
                task.runtime_owned_characters
                & earlier.runtime_owned_characters
                for earlier in earlier_pending
            ):
                earlier_pending.append(task)
                continue

            self._mark_running(task)

            future = asyncio.create_task(
                self._run_one(task),
                name=f"aether-task:{task.sequence}:{task.preset_key}",
            )
            running[future] = task
            busy.update(mine)
            launched = True

        return launched

    def _pending_all_waiting_for_locks(self) -> bool:
        with self._lock:
            pending = [
                task
                for task in self._tasks
                if task.status == "pending"
            ]
            blocked = set(self._blocked_characters)

        if not pending:
            return False

        return all(
            bool(set(task.owned_characters) & blocked)
            for task in pending
        )

    def _accel_settings_for_task(
        self,
        task: DungeonTask,
    ) -> tuple[AccelerationMode, float, int]:
        settings=load_runtime_settings()
        with self._lock:
            run_mode = self._run_mode

        acceleration_mode = resolve_effective_acceleration(
            task.acceleration,
            run_mode,
        )

        min_wait=float(settings.acceleration_balanced_min_wait_seconds)
        reserve=settings.acceleration_ticket_reserve

        if (
            run_mode == "rush"
            and settings.acceleration_rush_ignore_reserve
        ):
            reserve = 0

        return acceleration_mode, min_wait, reserve

    async def _run_one(
        self,
        task: DungeonTask,
    ) -> tuple[DungeonTask, bool, set[str]]:
        with self._lock:
            pool = dict(self._client_pool)

        preset = DUNGEON_PRESETS.get(task.preset_key)
        if preset is None:
            task.error = f"预设不存在：{task.preset_key}"
            return task, False, set()

        clients=[
            pool[username]
            for username in (
                task.runtime_owned_usernames
                if task.runtime_party_ready
                else task.owned_usernames
            )
        ]

        hooks = RuntimeHooks(
            choose_layout=None,
            choose_unknown_event=None,
            request_password=None,
            notify=None,
            on_state=lambda phase, data: self._on_task_state(
                task,
                phase,
                data,
            ),
            should_stop=self._stop_requested.is_set,
        )

        acceleration_mode, min_wait, reserve = (
            self._accel_settings_for_task(task)
        )

        ok = await asyncio.to_thread(
            run_preset,
            task.preset_key,
            clients=clients,
            hooks=hooks,
            allow_password_prompt=False,
            fast_mode=task.skip_camp_wait,
            acceleration_mode=acceleration_mode,
            accel_min_wait_seconds=min_wait,
            accel_ticket_reserve=reserve,
            skip_camp_wait=task.skip_camp_wait,
            resume_only=task.runtime_party_ready,
            expected_dungeon_id=task.dungeon_id,
        )

        blocked: set[str] = set()

        if not ok:
            errors=[client.last_error for client in clients if getattr(client,"last_error",None)]
            if errors and not task.error:
                task.error="；".join(errors)
            # 无论是异常失败还是用户暂停，都检查服务器是否仍有活动地下城。
            # 这是恢复时能否安全续跑的关键。
            active_clients=[
                client
                for client in clients
                if client.username in task.active_owned_characters
            ]
            blocked = await asyncio.to_thread(
                self._find_active_characters,
                active_clients,
            )

            if blocked and not self._stop_requested.is_set():
                task.error = (task.error+"；" if task.error else "")+(
                    "任务失败后仍有活动地下城或查询未成功，"
                    "相关角色已锁定："
                    + "，".join(sorted(blocked))
                )

        return task, ok, blocked

    @staticmethod
    def _find_active_characters(
        clients: list[AetherClient],
    ) -> set[str]:
        active: set[str] = set()

        for client in clients:
            result = client.get_current_dungeon(silent=True)
            if not isinstance(result, dict) or result.get("code",0)!=0 or "data" not in result:
                active.add(client.username)
                continue

            data = result.get("data")
            if not isinstance(data, dict):
                if data is not None:
                    active.add(client.username)
                continue

            if data.get("status") in {"lobby", "exploring"} and not data.get("completion_reason"):
                active.add(client.username)

        return active

    # ------------------------------------------------------------------
    # 状态变更（每次都 checkpoint）
    # ------------------------------------------------------------------

    def _on_task_state(
        self,
        task: DungeonTask,
        phase: str,
        data: dict[str, Any],
    ) -> None:
        with self._lock:
            task.phase = phase
            if phase=="runtime_party_ready":
                task.runtime_party_ready=True
            if data.get("dungeon_id"):
                task.dungeon_id=str(data["dungeon_id"])

            if data.get("node_name") is not None:
                task.node_name = str(data["node_name"])

            if data.get("node_index") is not None:
                try:
                    task.node_index = int(data["node_index"])
                except (TypeError, ValueError):
                    pass
            if "nodes" in data:
                task.nodes = normalize_runtime_nodes(data["nodes"])

        self._persist_checkpoint()

    def _mark_running(self, task: DungeonTask) -> None:
        with self._lock:
            task.status = "running"
            task.phase = "starting"
            task.started_at = time.time()
            task.finished_at = None
            task.error = None
            task.holds_resource_lock = False
            task.lock_reason = None
        self._persist_checkpoint()

    def _reset_failure_streaks_locked(self, task: DungeonTask) -> None:
        for username in task.owned_usernames:
            self._failure_streaks[username] = 0

    def _record_failure_locked(self, task: DungeonTask) -> bool:
        """记录一次“可继续调度”的普通失败；达到阈值后熔断该资源链。"""
        limit = self.failure_limit
        if limit <= 0:
            return False

        hit_limit = False
        for username in task.owned_usernames:
            streak = self._failure_streaks.get(username, 0) + 1
            self._failure_streaks[username] = streak
            if streak >= limit:
                hit_limit = True

        if not hit_limit:
            return False

        task.holds_resource_lock = True
        task.lock_reason = "failure_circuit_breaker"

        chars = "，".join(task.owned_usernames)
        suffix = (
            f"；同一资源链连续失败已达到 {limit} 次，"
            f"已暂停相关角色：{chars}"
        )
        task.error = (task.error or "地下城任务失败") + suffix
        return True

    def _finish_task(
        self,
        task: DungeonTask,
        *,
        success: bool,
        cancelled: bool = False,
        error: str | None = None,
    ) -> None:
        with self._lock:
            task.finished_at = time.time()

            if cancelled:
                task.status = "cancelled"
                task.phase = "cancelled"
            elif success:
                task.status = "success"
                task.phase = "completed"
                task.error = None
                task.holds_resource_lock = False
                task.lock_reason = None
                self._reset_failure_streaks_locked(task)
            else:
                task.status = "failed"
                task.phase = "failed"

            if error:
                task.error = error

            # 只有“原本不会锁角色”的普通失败才参与连续失败熔断。
            # 已经存在 active_dungeon / worker_exception 等锁时，按原保护逻辑处理。
            if (
                not success
                and not cancelled
                and not task.holds_resource_lock
            ):
                self._record_failure_locked(task)

            self._rebuild_blocked_characters_locked()

        self._persist_checkpoint()

    def _rebuild_blocked_characters(self) -> None:
        with self._lock:
            self._rebuild_blocked_characters_locked()
        self._persist_checkpoint()

    def _has_status(self, status: TaskStatus) -> bool:
        with self._lock:
            return any(task.status == status for task in self._tasks)

    def _set_last_message(self, message: str) -> None:
        with self._lock:
            self._last_message = message
        self._persist_checkpoint()

    # ------------------------------------------------------------------
    # 人工解决“不确定”任务
    # ------------------------------------------------------------------

    def retry_task(self, sequence: int) -> tuple[bool, str]:
        if self.running:
            return False, "批量调度器正在运行，先等待本轮结束或停止。"

        with self._lock:
            task = next(
                (
                    item
                    for item in self._tasks
                    if item.sequence == sequence
                ),
                None,
            )

            if task is None:
                return False, f"没有任务 #{sequence}。"

            if task.status == "success":
                return False, f"任务 #{sequence} 已成功，不会重复执行。"

            if task.status == "running":
                return (
                    False,
                    f"任务 #{sequence} 是上次中断时的 running 状态；"
                    "请直接 /aether 恢复，让程序先检查服务器。",
                )

            if task.preset_key not in DUNGEON_PRESETS:
                return False, f"当前配置中不存在预设：{task.preset_key}"

            # active_dungeon 不能直接转 pending，否则可能把不匹配地下城
            # 当作新任务重开。把它重新标成 running，让下一次 /恢复
            # 先走 _prepare_interrupted_tasks() 检查服务器。
            if task.lock_reason in {"active_dungeon", "paused_active"}:
                task.status = "running"
                task.phase = "recheck_required"
            else:
                # uncertain_completion 是用户明确选择“重打一把”；
                # 这时允许转 pending。
                task.status = "pending"
                task.phase = "pending"
                task.runtime_party_ready=False
                task.dungeon_id=None

            task.error = None
            task.finished_at = None
            task.holds_resource_lock = False
            task.lock_reason = None
            self._reset_failure_streaks_locked(task)
            self._rebuild_blocked_characters_locked()

        self._persist_checkpoint()

        return (
            True,
            f"任务 #{sequence} 已标记为重试。"
            "发送 /aether 恢复 继续调度。",
        )

    def skip_task(self, sequence: int) -> tuple[bool, str]:
        if self.running:
            return False, "批量调度器正在运行，先等待本轮结束或停止。"

        with self._lock:
            task = next(
                (
                    item
                    for item in self._tasks
                    if item.sequence == sequence
                ),
                None,
            )

            if task is None:
                return False, f"没有任务 #{sequence}。"

            if task.status == "success":
                return False, f"任务 #{sequence} 已成功，无需跳过。"

            if task.status == "running":
                return (
                    False,
                    f"任务 #{sequence} 是中断时 running；"
                    "先 /aether 恢复 让程序检查服务器状态。",
                )

            if task.lock_reason in {"active_dungeon", "paused_active"}:
                return (
                    False,
                    f"任务 #{sequence} 仍关联活动/不匹配地下城，"
                    "不能直接释放角色锁。\n"
                    "请先 /aether 重试 "
                    f"{sequence}，再 /aether 恢复 重新检查。",
                )

            task.status = "skipped"
            task.phase = "skipped"
            task.finished_at = time.time()
            task.error = "用户手动跳过"
            task.holds_resource_lock = False
            task.lock_reason = None
            self._reset_failure_streaks_locked(task)
            self._rebuild_blocked_characters_locked()

        self._persist_checkpoint()

        return (
            True,
            f"任务 #{sequence} 已跳过。"
            "如还有 pending 项，发送 /aether 恢复 继续。",
        )

    # ------------------------------------------------------------------
    # 停止 / 通知 / 状态
    # ------------------------------------------------------------------

    def _task_progress_text(self) -> str:
        with self._lock:
            tasks = list(self._tasks)

        success = sum(task.status == "success" for task in tasks)
        running = sum(task.status == "running" for task in tasks)
        pending = sum(task.status == "pending" for task in tasks)
        failed = sum(task.status == "failed" for task in tasks)
        uncertain = sum(task.status == "uncertain" for task in tasks)
        blocked = sum(task.status == "blocked" for task in tasks)
        skipped = sum(task.status == "skipped" for task in tasks)

        return (
            f"成功 {success}/{len(tasks)}"
            f" · 运行 {running}"
            f" · 等待 {pending}"
            f" · 失败 {failed}"
            f" · 不确定 {uncertain}"
            f" · 阻塞 {blocked}"
            f" · 跳过 {skipped}"
        )

    def _task_identity_text(self, task: DungeonTask) -> str:
        with self._lock:
            total = len(self._tasks)
            plan_name = self._plan_name or self._plan_key or "未知任务"

        preset = DUNGEON_PRESETS.get(task.preset_key)
        if preset is None:
            party_text = "未知"
        else:
            party_text = " -> ".join(
                (
                    member.username
                    if member.controlled
                    else f"{member.username}(好友)"
                )
                for member in preset.party
            )

        return (
            f"任务：#{task.sequence}/{total} "
            f"{task.preset_label} [{task.preset_key}]\n"
            f"计划：{plan_name}\n"
            f"队伍：{party_text}"
        )

    def _task_recovery_guide(self, event_type: str, task: DungeonTask) -> str:
        sequence = task.sequence

        if event_type == "uncertain":
            return (
                "现在先发：/aether 状态\n"
                f"确认这把没完成：/aether 重试 {sequence}\n"
                f"确认这把其实已完成：/aether 跳过 {sequence}\n"
                "做出选择后再发：/aether 恢复"
            )

        if event_type == "resume_ready":
            return (
                "服务器仍保留匹配的地下城，"
                "本次 /aether 恢复 会自动从当前进度续跑，无需额外操作。"
            )

        if event_type == "blocked":
            if task.lock_reason == "active_dungeon":
                return (
                    "检测到不匹配的活动地下城，先不要直接补打。\n"
                    "先检查/处理服务器上的当前地下城；处理完后：\n"
                    f"/aether 重试 {sequence}\n"
                    "/aether 恢复"
                )

            error = task.error or ""
            if "配置发生变化" in error:
                return (
                    "checkpoint 与当前 DungeonPreset 不一致。\n"
                    "如果要继续旧任务：先把该预设恢复成原配置，然后：\n"
                    f"/aether 重试 {sequence}\n"
                    "/aether 恢复\n"
                    f"如果确认不要这一项：/aether 跳过 {sequence}"
                )

            if "OAuth" in error or "Client" in error:
                return (
                    "先修复 OAuth/角色池问题，然后：\n"
                    f"/aether 重试 {sequence}\n"
                    "/aether 恢复"
                )

            return (
                "先发 /aether 状态 查看阻塞原因。\n"
                "处理原因后：\n"
                f"/aether 重试 {sequence}\n"
                "/aether 恢复"
            )

        if event_type == "failed":
            if task.lock_reason == "failure_circuit_breaker":
                return (
                    f"同一资源链已连续失败 {self.failure_limit} 次，"
                    "调度器已自动熔断这组角色；不冲突的其他任务会继续。\n"
                    "等本轮暂停/结束后，先确认失败原因已经处理，再发：\n"
                    f"/aether 重试 {sequence}\n"
                    "/aether 恢复"
                )

            if task.lock_reason == "active_dungeon":
                return (
                    "服务器仍有未结束地下城，相关角色已锁住。\n"
                    "当前不冲突的其他任务会继续。\n"
                    "等本轮暂停/结束后：\n"
                    f"/aether 重试 {sequence}\n"
                    "/aether 恢复\n"
                    "恢复时会先检查现有地下城，不会直接重开。"
                )

            if task.holds_resource_lock:
                return (
                    "相关角色已暂时锁住，不冲突的其他任务会继续。\n"
                    "等本轮暂停/结束后：\n"
                    f"/aether 重试 {sequence}\n"
                    "/aether 恢复"
                )

            return (
                "没有检测到需要锁定的活动地下城，后续任务可继续。\n"
                "如果之后想补打这一项，等本轮结束后：\n"
                f"/aether 重试 {sequence}\n"
                "/aether 恢复"
            )

        return ""

    def _format_task_event_message(
        self,
        event_type: str,
        task: DungeonTask,
    ) -> str:
        identity = self._task_identity_text(task)
        progress = self._task_progress_text()

        if event_type == "success":
            return (
                "Aether 任务完成\n"
                f"{identity}\n"
                f"进度：{progress}"
            )

        if event_type == "resume_ready":
            return (
                "Aether 恢复检查通过\n"
                f"{identity}\n"
                f"{self._task_recovery_guide(event_type, task)}"
            )

        if event_type == "uncertain":
            return (
                "Aether 任务状态不确定\n"
                f"{identity}\n"
                f"原因：{task.error or '无法确认中断前任务是否已结算'}\n"
                f"进度：{progress}\n"
                f"{self._task_recovery_guide(event_type, task)}"
            )

        if event_type == "blocked":
            return (
                "Aether 任务已阻塞\n"
                f"{identity}\n"
                f"原因：{task.error or '任务无法安全继续'}\n"
                f"进度：{progress}\n"
                f"{self._task_recovery_guide(event_type, task)}"
            )

        return (
            "Aether 任务失败\n"
            f"{identity}\n"
            f"阶段：{task.phase}\n"
            f"错误：{task.error or '地下城任务失败'}\n"
            f"进度：{progress}\n"
            f"{self._task_recovery_guide('failed', task)}"
        )

    async def _notify_task_event(
        self,
        event_type: str,
        task: DungeonTask,
    ) -> None:
        from .notifications import allows
        kind="error" if event_type in {"failed","blocked","uncertain"} else "detail"
        if not allows(kind):
            return
        key=(self._run_id,task.sequence,event_type,task.error,task.lock_reason)
        seen=getattr(self,"_notification_seen",set())
        if key in seen:
            return
        seen.add(key)
        self._notification_seen=seen
        await self._safe_notify(
            self._format_task_event_message(event_type, task),kind=kind
        )

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
            pass

    def request_stop(self) -> tuple[bool, str]:
        if not self.running:
            return False, "当前没有运行中的 Aether 批量任务。"

        self._stop_requested.set()
        return (
            True,
            "已请求停止批量任务；不会再启动新任务，"
            "正在运行的地下城会在安全节点暂停。",
        )

    def status_payload(self)->dict[str,Any]|None:
        running=self.running
        with self._lock:
            if not self._plan_key:
                return None
            tasks=[DungeonTask(**task.__dict__) for task in self._tasks]
            result=self._run_result_locked()
            plan_key=self._plan_key
            plan_name=self._plan_name
            run_mode=self._run_mode
            run_id=self._run_id
            started_at=self._started_at
            finished_at=self._finished_at
            archived_at=self._archived_at
            blocked_characters=sorted(self._blocked_characters)
            failure_streaks=dict(self._failure_streaks)
            last_message=self._last_message
            checkpoint_loaded=self._checkpoint_loaded
            checkpoint_error=self._checkpoint_error
        statuses=(
            "success","running","pending","uncertain",
            "failed","blocked","skipped","cancelled",
        )
        counts={
            status:sum(task.status==status for task in tasks)
            for status in statuses
        }
        unresolved=any(
            task.status in {"pending","running","uncertain","blocked"}
            or task.holds_resource_lock
            for task in tasks
        )
        return {
            "running":running,
            "recoverable":not running and unresolved,
            "run_id":run_id,
            "plan_key":plan_key,
            "plan_name":plan_name,
            "run_mode":run_mode,
            "result":result,
            "started_at":started_at,
            "finished_at":finished_at,
            "archived_at":archived_at,
            "last_message":last_message,
            "blocked_characters":blocked_characters,
            "failure_streaks":failure_streaks,
            "checkpoint_loaded":checkpoint_loaded,
            "checkpoint_error":checkpoint_error,
            "counts":counts,
            "tasks":[
                {
                    "sequence":task.sequence,
                    "preset_key":task.preset_key,
                    "preset_label":task.preset_label,
                    "status":task.status,
                    "phase":task.phase,
                    "node_name":task.node_name,
                    "node_index":task.node_index,
                    "nodes":list(task.nodes),
                    "started_at":task.started_at,
                    "finished_at":task.finished_at,
                    "error":task.error,
                    "owned_characters":list(task.owned_usernames),
                    "holds_resource_lock":task.holds_resource_lock,
                }
                for task in tasks
            ],
        }

    def status_text(self) -> str:
        with self._lock:
            plan_key = self._plan_key
            plan_name = self._plan_name
            run_mode = self._run_mode
            run_id = self._run_id
            started_at = self._started_at
            archived_at = self._archived_at
            failure_streaks = dict(self._failure_streaks)
            tasks = [
                DungeonTask(**task.__dict__)
                for task in self._tasks
            ]
            blocked = set(self._blocked_characters)
            last_message = self._last_message
            checkpoint_loaded = self._checkpoint_loaded
            checkpoint_error = self._checkpoint_error

        if not plan_key:
            if checkpoint_error:
                return f"Aether checkpoint 异常：{checkpoint_error}"
            return "Aether 批量任务：尚未运行。"

        counts = {
            status: sum(task.status == status for task in tasks)
            for status in (
                "success",
                "running",
                "pending",
                "uncertain",
                "failed",
                "blocked",
                "skipped",
                "cancelled",
            )
        }

        settings=load_runtime_settings()
        threshold=settings.acceleration_balanced_min_wait_seconds
        reserve=settings.acceleration_ticket_reserve

        lines = [
            f"Aether 批量任务：{plan_name} [{plan_key}]",
            f"运行 ID：{run_id or '-'}",
            (
                f"运行模式：{RUN_MODE_LABELS[run_mode]}"
                f" · 平衡阈值 {threshold}s"
                f" · 库存保护 {reserve}"
            ),
            f"总计：{len(tasks)}",
            (
                f"完成：{counts['success']}  "
                f"运行/中断：{counts['running']}  "
                f"等待：{counts['pending']}"
            ),
            (
                f"不确定：{counts['uncertain']}  "
                f"失败：{counts['failed']}  "
                f"阻塞：{counts['blocked']}"
            ),
            (
                f"跳过：{counts['skipped']}  "
                f"取消：{counts['cancelled']}"
            ),
        ]

        if started_at:
            elapsed = max(0, int(time.time() - started_at))
            minutes, seconds = divmod(elapsed, 60)
            lines.append(f"累计：{minutes}分{seconds:02d}秒")

        if checkpoint_loaded and not self.running:
            if counts["running"]:
                lines.extend([
                    "",
                    "检测到进程中断前仍有 running 任务。",
                    "发送 /aether 恢复，程序会先查询服务器后再决定是否续跑。",
                ])

        running_tasks = [
            task for task in tasks
            if task.status == "running"
        ]
        if running_tasks:
            lines.append("")
            lines.append(
                "运行中/中断时运行："
            )
            for task in running_tasks[:8]:
                chars = ",".join(task.owned_usernames)
                node = task.node_name or task.phase
                lines.append(
                    f"#{task.sequence} {task.preset_label} "
                    f"[{chars}] · {node}"
                )

        uncertain_tasks = [
            task for task in tasks
            if task.status == "uncertain"
        ]
        if uncertain_tasks:
            lines.extend([
                "",
                "需要你确认的不确定任务：",
            ])
            for task in uncertain_tasks[:8]:
                lines.append(
                    f"#{task.sequence} {task.preset_label}："
                    f"{task.error or '状态不确定'}"
                )
            lines.extend([
                "确认要补打一把：/aether 重试 <编号>",
                "确认已经打过：/aether 跳过 <编号>",
            ])

        if blocked:
            lines.append("")
            lines.append(
                "已锁定角色："
                + "，".join(sorted(blocked))
            )

        failures = [
            task
            for task in tasks
            if task.status in {"failed", "blocked"}
        ]
        if failures:
            lines.append("")
            lines.append("最近失败/阻塞：")
            for task in failures[-5:]:
                lines.append(
                    f"#{task.sequence} {task.preset_label}："
                    f"{task.error or task.status}"
                )

        active_streaks = {
            username: count
            for username, count in failure_streaks.items()
            if count > 0
        }
        if active_streaks:
            lines.append("")
            lines.append(
                "连续失败计数："
                + "，".join(
                    f"{username}={count}"
                    for username, count in sorted(active_streaks.items())
                )
                + f"（阈值 {self.failure_limit}）"
            )

        if last_message:
            lines.append("")
            lines.append(f"最近：{last_message}")

        lines.append("")
        lines.append(f"checkpoint：{self.checkpoint_path}")
        if archived_at is not None:
            lines.append(f"history：{self.history_dir}")

        return "\n".join(lines)
