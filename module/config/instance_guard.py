# This Python file uses the following encoding: utf-8
# @author handman123
# github https://github.com/runhey
"""跨进程实例看守器。

通过共享 JSON 状态文件协调多个进程的实例执行顺序，确保同一时间
只有一个实例操作模拟器。持有执行权（token）的实例可执行任务，
其他实例排队等待。
"""
import json
import threading
from pathlib import Path
from datetime import datetime

from filelock import FileLock
from module.logger import logger


class _QueueState:
    """共享状态文件的持久化层。

    负责 JSON 文件的原子读写和持有者心跳过期判断。
    文件锁（FileLock）保证跨进程写入安全。

    文件格式:
        {
            "current": "oas1",               # 当前持有执行权的实例名
            "timestamp": "2026-07-08 ...",   # 持有者心跳时间戳
            "queue": ["oas2", "oas3"]        # 等待队列
        }
    """

    STATE_FILE = Path.cwd() / "log" / ".queue_state.json"
    STALE_TIMEOUT = 300  # 心跳超时 5 分钟，超过视为持有者崩溃

    def __init__(self, config_name: str):
        """Args:
            config_name: 配置文件名称，如 'oas1'。
        """
        self.config_name = config_name
        self._lock = FileLock(str(self.STATE_FILE) + ".lock", timeout=5)

    def read(self) -> dict:
        """读取状态文件。

        调用方需持有 _lock。文件不存在或损坏时返回空状态。

        Returns:
            dict: 包含 current、timestamp、queue 的状态字典。
        """
        if not self.STATE_FILE.exists():
            return {"current": None, "timestamp": None, "queue": [],
                    "last_holder": None, "last_release": None}
        try:
            with open(self.STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("[InstanceGuard] State file corrupted, resetting")
            return {"current": None, "timestamp": None, "queue": [],
                    "last_holder": None, "last_release": None}

    def write(self, state: dict) -> None:
        """写入状态文件。调用方需持有 _lock。"""
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def is_stale(self, state: dict) -> bool:
        """判断持有者心跳是否过期。

        如果 timestamp 距现在超过 STALE_TIMEOUT 秒，认为持有者崩溃。

        Args:
            state: 从 read() 获取的状态字典。

        Returns:
            bool: True 表示心跳过期，可安全接管。
        """
        ts_str = state.get("timestamp")
        if not ts_str:
            return False
        try:
            ts = datetime.fromisoformat(ts_str)
            elapsed = (datetime.now() - ts).total_seconds()
            return elapsed > self.STALE_TIMEOUT
        except (ValueError, TypeError):
            return True

    def __enter__(self):
        self._lock.acquire()
        return self.read()

    def __exit__(self, *args):
        self._lock.release()


class _Heartbeat:
    """心跳保活线程。

    持有 token 期间定期更新 timestamp，防止被误判崩溃。
    同时监控 token 是否被其他实例抢占（例如被管理员从状态文件强制接管），
    检测到丢失时设置 token_lost 标志通知主线程。
    """

    INTERVAL = 180  # 心跳间隔 3 分钟，小于 STALE_TIMEOUT(5min) 留出缓冲

    def __init__(self, config_name: str, state: _QueueState):
        self._config_name = config_name
        self._state = state
        self._thread: threading.Thread = None
        self._stop_event: threading.Event = None
        self._token_lost = threading.Event()

    @property
    def token_lost(self) -> bool:
        """token 是否被其他实例抢占。"""
        return self._token_lost.is_set()

    def start(self) -> None:
        """启动心跳 daemon 线程。已运行则跳过。"""
        if self._thread and self._thread.is_alive():
            return
        self._token_lost.clear()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(
            f"[InstanceGuard] Heartbeat started for '{self._config_name}'")

    def stop(self) -> None:
        """停止心跳线程。"""
        if self._stop_event:
            self._stop_event.set()
        self._thread = None
        self._stop_event = None

    def _loop(self) -> None:
        """心跳循环。每 INTERVAL 秒刷新 timestamp。"""
        while not self._stop_event.wait(timeout=self.INTERVAL):
            try:
                with self._state._lock:
                    state = self._state.read()
                    if state["current"] == self._config_name:
                        state["timestamp"] = datetime.now().isoformat()
                        self._state.write(state)
                    elif self._config_name not in state.get("queue", []):
                        # 不在 current 也不在 queue，说明被强制移除了
                        logger.warning(
                            f"[InstanceGuard] '{self._config_name}' lost token, "
                            f"current holder: {state['current']}")
                        self._token_lost.set()
                        return
            except Exception as e:
                logger.error(f"[InstanceGuard] Heartbeat error: {e}")


class InstanceGuard:
    """跨进程实例看守器。

    通过共享状态文件协调多个实例的执行顺序，确保同一时间只有一个实例
    操作模拟器。集成心跳保活和崩溃检测。

    用法:
        guard = InstanceGuard(config_name)
        if guard.try_acquire():
            # 执行业务逻辑
            guard.release()
    """

    def __init__(self, config_name: str, stagger_group: list[str] | None = None,
                 gap_minutes: int = 0):
        """Args:
            config_name: 配置文件名称。
            stagger_group: 错峰分组成员配置名，例如 ['oas1', 'oas3']。
            gap_minutes: 上一个同组成员释放执行权后，至少间隔多少分钟才允许开始。
        """
        self.config_name = config_name
        self._state = _QueueState(config_name)
        self._heartbeat = _Heartbeat(config_name, self._state)
        self._stagger_group = [name for name in (stagger_group or []) if name]
        self._gap_seconds = max(0, int(gap_minutes)) * 60

    @property
    def token_lost(self) -> bool:
        """token 是否被其他实例抢占。"""
        return self._heartbeat.token_lost

    def _should_wait_gap(self, state: dict) -> bool:
        """错峰判断：同组上一个实例刚释放执行权时，是否还没到最小间隔。

        调用方需持有 _lock。没有错峰设置、上一个持有者是自己、或不在同组时，
        都直接放行。
        """
        if not self._stagger_group or self._gap_seconds <= 0:
            return False
        last_holder = state.get("last_holder")
        last_release = state.get("last_release")
        if not last_holder or last_holder == self.config_name:
            return False
        if last_holder not in self._stagger_group:
            return False
        if not last_release:
            return False
        try:
            released_at = datetime.fromisoformat(last_release)
        except (ValueError, TypeError):
            return False
        waited = (datetime.now() - released_at).total_seconds()
        if waited < self._gap_seconds:
            remain = int(self._gap_seconds - waited)
            logger.info(
                f"[Stagger] '{last_holder}' released {int(waited)}s ago, "
                f"'{self.config_name}' waits {remain}s more")
            return True
        return False

    def _resume_not_reached(self, state: dict) -> bool:
        """交接后的强制间隔是否还没到点。

        上一个持有者把执行权交给等待队列里的同组实例时，会写入 resume_at，
        在这之前任何人都不能抢占（包括心跳过期接管）。
        """
        resume_at = state.get("resume_at")
        if not resume_at:
            return False
        try:
            return datetime.now() < datetime.fromisoformat(resume_at)
        except (ValueError, TypeError):
            return False

    # ==================== 执行权操作 ====================

    def try_acquire(self) -> bool:
        """尝试获取执行权。

        四种情况:
        1. 自己已是持有者 — 刷新 heartbeat，返回 True
        2. 持有者心跳过期 — 强制接管，返回 True
        3. 无人持有 — 自己成为持有者，启动心跳，返回 True
        4. 他人持有 — 加入等待队列，返回 False

        Returns:
            True: 已获得执行权。
            False: 执行权被他人持有，已加入队列。
        """
        with self._state._lock:
            state = self._state.read()

            # 交接间隔未到：谁都不能开始
            if self._resume_not_reached(state):
                return False

            # 自己已是持有者，刷新心跳
            if state["current"] == self.config_name:
                state["timestamp"] = datetime.now().isoformat()
                state["resume_at"] = None
                self._state.write(state)
                self._heartbeat.start()
                logger.info(f"[InstanceGuard] '{self.config_name}' already holds token")
                return True

            # 持有者崩溃，强制接管
            if state["current"] and self._state.is_stale(state):
                logger.warning(
                    f"[InstanceGuard] Holder '{state['current']}' "
                    f"heartbeat stale, taking over")
                state["current"] = None
                state["timestamp"] = None

            # 无人持有，先检查错峰间隔，未到点则继续等待
            if state["current"] is None and self._should_wait_gap(state):
                return False

            # 无人持有，自己成为持有者
            if state["current"] is None:
                state["current"] = self.config_name
                state["timestamp"] = datetime.now().isoformat()
                if self.config_name in state["queue"]:
                    state["queue"].remove(self.config_name)
                self._state.write(state)
                logger.info(
                    f"[InstanceGuard] '{self.config_name}' acquired token")
                self._heartbeat.start()
                return True

            # 他人持有，加入等待队列
            if self.config_name not in state["queue"]:
                state["queue"].append(self.config_name)
                self._state.write(state)
                logger.info(
                    f"[InstanceGuard] '{self.config_name}' waiting, "
                    f"holder: '{state['current']}', "
                    f"queue: {state['queue']}")
            return False

    def release(self) -> None:
        """释放执行权。

        - 等待队列非空时，把执行权交给队首实例，并写入 resume_at（错峰间隔），
          保证它不会立刻开跑；
        - 队列为空时清空 current，记录最后一次释放时间；
        - 如果自己不是持有者，静默返回。
        """
        with self._state._lock:
            state = self._state.read()
            if state["current"] != self.config_name:
                return

            self._heartbeat.stop()
            now = datetime.now()
            state["last_holder"] = self.config_name
            state["last_release"] = now.isoformat()
            if state["queue"]:
                next_holder = state["queue"].pop(0)
                state["current"] = next_holder
                state["timestamp"] = now.isoformat()
                if self._gap_seconds > 0:
                    resume_at = now.timestamp() + self._gap_seconds
                    state["resume_at"] = datetime.fromtimestamp(resume_at).isoformat()
                logger.info(
                    f"[InstanceGuard] '{self.config_name}' released token "
                    f"→ '{next_holder}' (stagger gap {self._gap_seconds // 60}min)")
            else:
                state["current"] = None
                state["timestamp"] = None
                state["resume_at"] = None
                logger.info(f"[InstanceGuard] '{self.config_name}' released token")
            self._state.write(state)

    def should_release(self, pending_task: list, waiting_task: list,
                       idle_threshold_minutes: int = 10) -> bool:
        """判断是否应该在进入空闲前释放执行权。

        条件:
        1. pending_task 为空（当前无待执行任务）
        2. waiting_task 为空，或最早的任务距现在超过 idle_threshold_minutes 分钟

        Args:
            pending_task: 当前到期的任务列表。
            waiting_task: 未来任务列表，按 next_run 升序。
            idle_threshold_minutes: 空闲阈值（分钟）。

        Returns:
            True: 空闲时间足够长，应释放执行权。
            False: 即将有任务，应继续持有。
        """
        if pending_task:
            return False
        if not waiting_task:
            return True

        next_task_time = waiting_task[0].next_run
        idle_seconds = (next_task_time - datetime.now()).total_seconds()
        return idle_seconds > idle_threshold_minutes * 60

    def remove_from_queue(self) -> None:
        """从排队系统中完全移除自己。

        进程停止时调用，防止残留状态导致死锁。
        如果自己是持有者，将执行权移交给下一个等待者。
        """
        with self._state._lock:
            state = self._state.read()

            if self.config_name in state["queue"]:
                state["queue"].remove(self.config_name)
                logger.info(
                    f"[InstanceGuard] '{self.config_name}' removed from queue")

            if state["current"] == self.config_name:
                self._heartbeat.stop()
                if state["queue"]:
                    next_holder = state["queue"].pop(0)
                    state["current"] = next_holder
                    state["timestamp"] = datetime.now().isoformat()
                    logger.info(
                        f"[InstanceGuard] '{self.config_name}' removed, "
                        f"token → '{next_holder}'")
                else:
                    state["current"] = None
                    state["timestamp"] = None
                state["last_holder"] = self.config_name
                state["last_release"] = datetime.now().isoformat()
                self._state.write(state)
                return

            self._state.write(state)
