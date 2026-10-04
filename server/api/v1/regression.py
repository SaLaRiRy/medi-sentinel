"""TICKET-023：回归基线对外接口（`SPEC.md` 5.4「可观测性与回归」）。

- `POST /regression/runs` → `{run_id}`（提交一次回放）
- `GET /regression/runs/{run_id}` → `{status, metrics: MetricsReport|null}`（轮询）
- `GET /regression/baselines` → `BaselineView[]`（可用基线版本清单）

三个端点均要求 `admin`。回放是长任务，提交与轮询分开（异步 job，见
`regression.runs`），handler 本身只做校验与查询，不把回放按在请求路径上。
"""

from datetime import datetime

import anyio
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from core.deps import Principal, require_admin
from core.errors import ApiError
from core.response import Envelope, error_responses, success
from core.serialization import ApiDateTime
from regression.metrics import MetricsReport
from regression.runs import RegressionRuns
from regression.schema import BaselineMissing, CaseSetMissing

router = APIRouter(tags=["regression"])


class RegressionRunRequest(BaseModel):
    case_set_version: str
    baseline_version: str
    label: str | None = None


class RegressionRunStartView(BaseModel):
    run_id: str


class RegressionRunView(BaseModel):
    status: str
    metrics: MetricsReport | None = None


class BaselineView(BaseModel):
    baseline_version: str
    case_set_version: str
    case_count: int
    created_at: ApiDateTime


def _runs(request: Request) -> RegressionRuns:
    return request.app.state.regression_runs


@router.post(
    "/regression/runs",
    response_model=Envelope[RegressionRunStartView],
    responses=error_responses(401, 403, 404, 422),
)
async def start_run(
    payload: RegressionRunRequest,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> Envelope[RegressionRunStartView]:
    runs = _runs(request)
    try:
        # 版本存在性检查要读磁盘；请求路径内不得出现同步阻塞 I/O（SPEC.md 3.1）。
        await anyio.to_thread.run_sync(
            runs.validate, payload.case_set_version, payload.baseline_version
        )
    except (CaseSetMissing, BaselineMissing) as error:
        raise ApiError(404, "用例集或基线版本不存在") from error
    run_id = runs.submit(
        case_set_version=payload.case_set_version,
        baseline_version=payload.baseline_version,
    )
    return success(RegressionRunStartView(run_id=run_id))


@router.get(
    "/regression/runs/{run_id}",
    response_model=Envelope[RegressionRunView],
    responses=error_responses(401, 403, 404),
)
async def read_run(
    run_id: str,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> Envelope[RegressionRunView]:
    state = _runs(request).get(run_id)
    if state is None:
        raise ApiError(404, "回放任务不存在")
    return success(RegressionRunView(status=state.status, metrics=state.metrics))


@router.get(
    "/regression/baselines",
    response_model=Envelope[list[BaselineView]],
    responses=error_responses(401, 403),
)
async def list_baselines(
    request: Request,
    principal: Principal = Depends(require_admin),
) -> Envelope[list[BaselineView]]:
    return success(
        [
            BaselineView(
                baseline_version=baseline.version,
                case_set_version=baseline.case_set_version,
                case_count=len(baseline.cases),
                created_at=datetime.fromisoformat(baseline.created_at),
            )
            for baseline in await anyio.to_thread.run_sync(_runs(request).baselines)
        ]
    )
