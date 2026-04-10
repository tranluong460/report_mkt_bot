import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime

from bot.config import VN_TZ

MAX_QUEUE_SIZE = 5


@dataclass
class BuildJob:
    build_id: int
    project: str
    branch: str
    user_id: str
    user_name: str
    chat_id: int
    thread_id: int | None
    message_id: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(VN_TZ).isoformat())


class BuildQueue:
    def __init__(self):
        self._queue: queue.Queue[BuildJob] = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self._lock = threading.Lock()
        self._current: BuildJob | None = None
        self._pending: list[BuildJob] = []

    def put(self, job: BuildJob) -> tuple[bool, int]:
        """Thêm job vào hàng đợi. Trả về (thành công, vị trí)."""
        with self._lock:
            if len(self._pending) >= MAX_QUEUE_SIZE:
                return False, 0
            self._pending.append(job)
            self._queue.put(job)
            return True, len(self._pending)

    def get(self, timeout: float = 1.0) -> BuildJob | None:
        """Lấy job tiếp theo. Trả về None nếu trống."""
        try:
            job = self._queue.get(timeout=timeout)
            with self._lock:
                if job in self._pending:
                    self._pending.remove(job)
                self._current = job
            return job
        except queue.Empty:
            return None

    def done(self) -> None:
        """Đánh dấu job hiện tại đã xong."""
        with self._lock:
            self._current = None

    def cancel(self, build_id: int) -> bool:
        """Huỷ job trong hàng đợi theo build ID. Không huỷ được job đang chạy."""
        with self._lock:
            for job in self._pending:
                if job.build_id == build_id:
                    self._pending.remove(job)
                    items = []
                    while not self._queue.empty():
                        try:
                            items.append(self._queue.get_nowait())
                        except queue.Empty:
                            break
                    for item in items:
                        if item.build_id != build_id:
                            self._queue.put(item)
                    return True
            return False

    def get_status(self) -> dict:
        """Lấy trạng thái hàng đợi."""
        with self._lock:
            return {
                "current": self._current,
                "pending": list(self._pending),
                "size": len(self._pending),
            }
