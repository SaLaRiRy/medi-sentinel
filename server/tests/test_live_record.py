"""TICKET-AC-10：录制的端口注入点与「不许覆盖既有基线」守卫。

全部离线：注入用的都是假端口，不碰 Neo4j / 向量索引 / 网络；录制目录一律用
`tmp_path`，绝不碰已提交的 `regression/baselines/`。
"""

import json
from pathlib import Path

import pytest

from regression.record import fixture_ports, record_case_set
from regression.schema import BaselineExists, CaseSet, RegressionCase, RegressionStore
from scripts import regression as regression_script


def _case_set(version: str = "t1", *, cases: int = 1) -> CaseSet:
    return CaseSet(
        version=version,
        cases=[
            RegressionCase(
                id=f"c{index}",
                group="llm",
                message="我头疼",
                session_id=index,
                answer=[f"回答{index}"],
            )
            for index in range(1, cases + 1)
        ],
    )


class FakeGraph:
    async def infer_diseases(self, symptoms):
        return [{"disease": "由工厂注入", "matched_symptoms": list(symptoms)}]


class FakeRetrieval:
    async def search(self, query, top_k=5):
        return [
            {
                "content": "由工厂注入的正文",
                "metadata": {"file_name": "注入.md"},
                "distance": 0.1,
            }
        ]


class FakeLlm:
    async def stream(self, prompt):
        yield "注入的分块"


class CountingFactory:
    """记录调用次数与返回的对象，验证「同一批实例」这条约定。"""

    def __init__(self):
        self.graph = FakeGraph()
        self.retrieval = FakeRetrieval()
        self.llm = FakeLlm()
        self.calls = 0

    def __call__(self, case):
        self.calls += 1
        return self.graph, self.retrieval, self.llm


# --- 注入点 -------------------------------------------------------------------


async def test_the_default_factory_is_still_the_offline_fixture():
    """不传工厂时行为与 TICKET-023 完全一致——8 处既有调用零改动。"""
    baseline = await record_case_set(_case_set())

    assert baseline.cases[0].llm_chunks == [["回答1"]]
    assert isinstance(baseline.cases[0].ports["retrieval"], list)


async def test_a_ports_factory_is_used_for_every_case():
    factory = CountingFactory()

    baseline = await record_case_set(_case_set(cases=2), ports_factory=factory)

    assert factory.calls == 2
    assert baseline.cases[0].llm_chunks == [["注入的分块"]]
    assert (
        baseline.cases[0].ports["retrieval"][0][0]["metadata"]["file_name"]
        == "注入.md"
    )
    assert baseline.cases[0].ports["graph"][0][0]["disease"] == "由工厂注入"


async def test_the_factory_returns_one_shared_set_of_ports():
    """真实适配器昂贵且有状态：工厂必须复用同一批实例，不能逐条重连。"""
    factory = CountingFactory()
    seen: list[tuple[int, int, int]] = []

    def wrapped(case):
        graph, retrieval, llm = factory(case)
        seen.append((id(graph), id(retrieval), id(llm)))
        return graph, retrieval, llm

    await record_case_set(_case_set(cases=3), ports_factory=wrapped)

    assert len(set(seen)) == 1


def test_fixture_ports_is_the_documented_default():
    import inspect

    from regression import record as record_module

    for function in (record_module.record_case, record_module.record_case_set):
        default = inspect.signature(function).parameters["ports_factory"].default
        assert default is record_module.fixture_ports
        assert default is fixture_ports


# --- 写守卫：不许覆盖既有基线 -------------------------------------------------


def test_ensure_writable_refuses_an_existing_version(tmp_path):
    store = RegressionStore(
        cases_dir=tmp_path / "cases", baselines_dir=tmp_path / "baselines"
    )
    store.ensure_writable("v1")  # 不存在 → 放行
    store.target_path("v1").parent.mkdir(parents=True, exist_ok=True)
    store.target_path("v1").write_text("{}", encoding="utf-8")

    with pytest.raises(BaselineExists) as error:
        store.ensure_writable("v1")

    assert error.value.version == "v1"
    assert store.ensure_writable("v1", force=True) == store.target_path("v1")


async def test_write_baseline_refuses_to_overwrite_without_force(tmp_path):
    store = RegressionStore(
        cases_dir=tmp_path / "cases", baselines_dir=tmp_path / "baselines"
    )
    baseline = await record_case_set(_case_set())
    store.write_baseline(baseline, version="t1")

    with pytest.raises(BaselineExists):
        store.write_baseline(baseline, version="t1")

    assert store.write_baseline(baseline, version="t1", force=True).is_file()


# --- CLI 守卫 -----------------------------------------------------------------


def _write_case_set(directory: Path, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{payload['version']}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _payload(version: str = "t1") -> dict:
    return {
        "version": version,
        "cases": [
            {
                "id": "c1",
                "group": "red_flag",
                "message": "胸口剧痛，出冷汗，喘不上气",
                "session_id": 1,
                "answer": [],
            }
        ],
    }


def _argv(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "record",
        "--case-set",
        "t1",
        "--baseline-version",
        "t1",
        "--cases-dir",
        str(tmp_path / "cases"),
        "--baselines-dir",
        str(tmp_path / "baselines"),
        *extra,
    ]


def test_live_without_a_baseline_version_is_rejected(tmp_path, capsys):
    """--live 必须与显式版本号绑定（argparse 层就拦下，不给默认值）。"""
    _write_case_set(tmp_path / "cases", _payload())

    with pytest.raises(SystemExit) as error:
        regression_script.main(
            [
                "record",
                "--case-set",
                "t1",
                "--live",
                "--cases-dir",
                str(tmp_path / "cases"),
                "--baselines-dir",
                str(tmp_path / "baselines"),
            ]
        )

    assert error.value.code == 2


def test_record_refuses_to_clobber_an_existing_baseline(tmp_path, capsys):
    _write_case_set(tmp_path / "cases", _payload())

    first = regression_script.main(_argv(tmp_path))
    second = regression_script.main(_argv(tmp_path))
    forced = regression_script.main(_argv(tmp_path, "--force"))

    assert first == 0
    assert second == 1
    assert "已存在" in capsys.readouterr().err
    assert forced == 0


def test_the_guard_covers_the_committed_versions(tmp_path):
    """`--live --baseline-version v1` 这种手滑必须被拦住。"""
    store = RegressionStore(
        cases_dir=tmp_path / "cases", baselines_dir=tmp_path / "baselines"
    )
    for version in ("v1", "v2"):
        store.ensure_writable(version)
        store.target_path(version).parent.mkdir(parents=True, exist_ok=True)
        store.target_path(version).write_text("{}", encoding="utf-8")

    for version in ("v1", "v2"):
        with pytest.raises(BaselineExists):
            store.ensure_writable(version)


def test_the_regression_package_never_imports_a_real_adapter():
    """注入只能从 scripts 侧来；`regression/` 整包保持零外部依赖。

    用 AST 看**真的 import**，不扫文本——`ports.py` 的文档里就写着
    "deliberately free of adapters / neo4j / chroma"，文本扫描会把它自己扫出来。
    """
    import ast

    root = Path(__file__).resolve().parents[1] / "regression"
    forbidden = {"adapters", "neo4j", "chromadb", "langchain"}
    for path in root.glob("*.py"):
        modules: list[str] = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        offenders = [
            module for module in modules if module.split(".")[0] in forbidden
        ]
        assert not offenders, f"{path.name} 引入了 {offenders}"
