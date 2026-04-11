"""Thread-safe build queue với cancel."""

import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime

from bot.config import VN_TZ
from bot.constants import MAX_QUEUE_SIZE


@dataclass
class BuildJob:
    build_id: int
    project: str
    branch: str
    user_id: str
    user_name: str
    chat_id: int
    thread_id: int | None
    message_id: int | None = None    # message zip
    message_id_2: int | None = None  # message yml (nếu dùng)
    created_at: str = field(
        default_factory=lambda: datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
    )


class BuildQueue:
    def __init__(self):
        self._queue: queue.Queue[BuildJob] = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self._lock = threading.Lock()
        self._current: BuildJob | None = None
        self._pending: list[BuildJob] = []

    def put(self, job: BuildJob) -> tuple[bool, int]:
        """Thêm job. Trả về (success, position)."""
        with self._lock:
            if len(self._pending) >= MAX_QUEUE_SIZE:
                return False, 0
            self._pending.append(job)
            self._queue.put(job)
            return True, len(self._pending)

    def get(self, timeout: float = 1.0) -> BuildJob | None:
        """Lấy job tiếp theo. None nếu queue rỗng."""
        try:
            job = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        with self._lock:
            if job in self._pending:
                self._pending.remove(job)
            self._current = job
        return job

    def done(self) -> None:
        with self._lock:
            self._current = None

    def cancel(self, build_id: int) -> bool:
        """Huỷ job trong pending (không huỷ được job đang chạy)."""
        with self._lock:
            target = next((j for j in self._pending if j.build_id == build_id), None)
            if not target:
                return False
            self._pending.remove(target)

            # Rebuild queue bỏ target
            remaining = []
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item.build_id != build_id:
                        remaining.append(item)
                except queue.Empty:
                    break
            for item in remaining:
                self._queue.put(item)
            return True

    def get_status(self) -> dict:
        with self._lock:
            return {
                "current": self._current,
                "pending": list(self._pending),
                "size": len(self._pending),
            }
