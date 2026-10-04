"""进程内回放任务注册表（ticket 023 §6，仿 `services/knowledge.py:KnowledgeJobs`）。

`POST /regression/runs` 只回 `{run_id}`，`GET /regression/runs/{run_id}` 回
`{status, metrics}` —— 提交-轮询是 SPEC.md 5.3/5.4 定死的模型，且回放是长任务，
不能按在请求路径上（SPEC.md 3.1）。后台任务在事件循环里跑，按 `run_id` 记
`pending | running | succeeded | failed`。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Literal

from regression.metrics import JudgePort, MetricsReport
from regression.replay import run_regression
from regression.schema import Baseline, RegressionStore

RunStatus = Literal["pending", "running", "succeeded", "failed"]

JobScheduler = Callable[[Coroutine[Any, Any, None]], "asyncio.Task[None]"]


@dataclass
class RegressionRunState:
    run_id: str
    status: RunStatus = "pending"
    metrics: MetricsReport | None = None
    error: str | None = None


class RegressionRuns:
    """The regression job seam: submit a version pair, poll by `run_id`."""

    def __init__(
        self,
        *,
        store: RegressionStore,
        judge: JudgePort | None = None,
        scheduler: JobScheduler | None = None,
    ) -> None:
        self._store = store
        self._judge = judge
        self._scheduler: JobScheduler = scheduler or asyncio.create_task
        self._runs: dict[str, RegressionRunState] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def validate(self, case_set_version: str, baseline_version: str) -> None:
        """Check both versions exist (sync; the API offloads it to a thread).

        `CaseSetMissing` / `BaselineMissing` propagate so the API can answer 404
        (SPEC.md 5.4：POST 的 404 = case set 或 baseline 版本不存在).
        """
        self._store.load_case_set(case_set_version)
        self._store.load_baseline(baseline_version)

    def submit(self, *, case_set_version: str, baseline_version: str) -> str:
        """Register a run and schedule its replay on the event loop."""
        run_id = uuid.uuid4().hex
        self._runs[run_id] = RegressionRunState(run_id=run_id)
        task = self._scheduler(self._execute(run_id, baseline_version))
        self._tasks.add(task)
        add_done_callback = getattr(task, "add_done_callback", None)
        if callable(add_done_callback):
            add_done_callback(self._tasks.discard)
        return run_id

    def get(self, run_id: str) -> RegressionRunState | None:
        return self._runs.get(run_id)

    def baselines(self) -> list[Baseline]:
        return self._store.list_baselines()

    async def _execute(self, run_id: str, baseline_version: str) -> None:
        state = self._runs[run_id]
        state.status = "running"
        try:
            baseline = self._store.load_baseline(baseline_version)
            state.metrics = await run_regression(baseline, judge=self._judge)
        except Exception as error:  # noqa: BLE001 - 失败记进任务状态，不抛到请求路径
            state.status = "failed"
            state.error = f"{type(error).__name__}: {error}"
        else:
            state.status = "succeeded"
