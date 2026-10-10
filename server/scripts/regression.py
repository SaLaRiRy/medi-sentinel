"""回归基线框架的命令面：`record` 录制、`replay` 回放对比（TICKET-023）。

Run from `server/`:
    .venv\\Scripts\\python.exe scripts\\regression.py record --case-set v1 --baseline-version v1
    .venv\\Scripts\\python.exe scripts\\regression.py replay --case-set v1 --baseline-version v1

脚本只做 argparse 薄壳，真正的 API 是可测的包函数（`regression.record` /
`regression.replay`）。`replay` 打印 `MetricsReport` JSON，遇阻断性失败
（拦截率 < 100% 或误拦率 > 0%）非零退出。`--cases-dir/--baselines-dir` 可覆盖，
便于测试不碰已提交的数据。
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from regression.metrics import JudgePort  # noqa: E402
from regression.metrics import compare_reports  # noqa: E402
from regression.record import record_case_set  # noqa: E402
from regression.replay import run_regression  # noqa: E402
from regression.retrieval_eval import evaluate_retrieval, load_case_set  # noqa: E402
from regression.retrieval_eval import RetrievalCaseSet, RetrievalReport  # noqa: E402
from regression.schema import (  # noqa: E402
    BaselineMissing,
    CaseSetMissing,
    RegressionStore,
    default_store,
)


def _store(cases_dir: str | None, baselines_dir: str | None) -> RegressionStore:
    base = default_store()
    return RegressionStore(
        cases_dir=Path(cases_dir) if cases_dir else base.cases_dir,
        baselines_dir=Path(baselines_dir) if baselines_dir else base.baselines_dir,
    )


def _judge(enabled: bool) -> JudgePort | None:
    """The CLI judge seam (ticket 023 §4).

    The application default has no model adapter, so `--judge` wires the LLM
    judge over `UnavailableLlmPort`: the judged layer is skipped and the report
    says `judge_available: false`. Tests inject a deterministic stub at the
    `regression.metrics.hallucination(..., judge=...)` seam instead.
    """
    if not enabled:
        return None
    from regression.ports import LlmJudgePort
    from skills.ports import UnavailableLlmPort

    return LlmJudgePort(UnavailableLlmPort())


def _add_dirs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cases-dir", default=None, help="用例集目录（默认 regression/cases）")
    parser.add_argument(
        "--baselines-dir", default=None, help="基线目录（默认 regression/baselines）"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="回归基线框架：录制与回放对比")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="离线录制一份版本化基线")
    record.add_argument("--case-set", required=True)
    record.add_argument("--baseline-version", required=True)
    _add_dirs(record)

    replay = sub.add_parser("replay", help="回放基线并输出 MetricsReport")
    replay.add_argument("--case-set", required=True)
    replay.add_argument("--baseline-version", required=True)
    replay.add_argument("--report", default=None, help="把 MetricsReport 另存为 JSON")
    replay.add_argument(
        "--compare",
        default=None,
        help="与另一基线版本对比，另打印其 MetricsReport 与差值（换模型工作流）",
    )
    replay.add_argument(
        "--judge", action="store_true", help="启用判定层（无模型适配器时降级为不可用）"
    )
    _add_dirs(replay)

    evaluate = sub.add_parser(
        "retrieval-eval", help="跑检索质量评测（recall@k / MRR，TICKET-AC-03）"
    )
    evaluate.add_argument(
        "--set", required=True, help="标注集版本名，如 retrieval-v1（默认在 regression/cases/）"
    )
    evaluate.add_argument("--report", default=None, help="把 RetrievalReport 另存为 JSON")
    evaluate.add_argument("--cases-dir", default=None, help="标注集目录（默认 regression/cases）")
    return parser


def _record(args: argparse.Namespace) -> int:
    store = _store(args.cases_dir, args.baselines_dir)
    case_set = store.load_case_set(args.case_set)
    baseline = asyncio.run(record_case_set(case_set))
    path = store.write_baseline(baseline, version=args.baseline_version)
    print(f"已录制基线 {args.baseline_version}：{len(baseline.cases)} 条用例 → {path}")
    return 0


async def _evaluate_and_close(
    retriever: object, case_set: RetrievalCaseSet
) -> RetrievalReport:
    """跑一次评测并释放端口持有的 HTTP 客户端。"""
    try:
        return await evaluate_retrieval(retriever, case_set)  # type: ignore[arg-type]
    finally:
        close = getattr(retriever, "close", None)
        if callable(close):
            await close()


def _retrieval_eval(args: argparse.Namespace) -> int:
    """检索质量评测：跑**真实**检索端口（需要嵌入服务），把标注集跑成三项指标。"""
    from adapters import build_vector_store
    from core.config import get_settings

    case_set = load_case_set(
        args.set, cases_dir=Path(args.cases_dir) if args.cases_dir else None
    )
    report = asyncio.run(
        _evaluate_and_close(build_vector_store(get_settings()), case_set)
    )
    text = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


def _replay(args: argparse.Namespace) -> int:
    store = _store(args.cases_dir, args.baselines_dir)
    store.load_case_set(args.case_set)  # 404-equivalent: the version must exist
    baseline = store.load_baseline(args.baseline_version)
    report = asyncio.run(run_regression(baseline, judge=_judge(args.judge)))
    payload = report.model_dump(mode="json")
    if args.compare:
        compared = store.load_baseline(args.compare)
        compared_report = asyncio.run(
            run_regression(compared, judge=_judge(args.judge))
        )
        payload = {
            "metrics": payload,
            "compared_baseline_version": args.compare,
            "compared_metrics": compared_report.model_dump(mode="json"),
            "delta": compare_reports(report, compared_report),
        }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8", newline="\n")

    if report.redflag_intercept_rate < 1.0:
        print(
            f"阻断性失败：红旗拦截率 {report.redflag_intercept_rate:.2%} < 100%",
            file=sys.stderr,
        )
        return 1
    if report.redflag_false_positive_rate > 0.0:
        print(
            f"阻断性失败：误拦率 {report.redflag_false_positive_rate:.2%} > 0%",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "record":
            return _record(args)
        if args.command == "retrieval-eval":
            return _retrieval_eval(args)
        return _replay(args)
    except (CaseSetMissing, BaselineMissing) as error:
        print(f"回放失败：{error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 - 命令面把异常转成非零退出
        print(f"回归框架失败：{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
