"""AC-B-34/35: the two commands — `record` and `replay`.

The script is a thin argparse shell over the package functions; the test drives
`main()` with overridable dirs so it never touches the committed data.
"""

import json

from scripts import regression as regression_script


def _write_case_set(directory, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{payload['version']}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _case_set(version: str = "t1", *, red_flag: bool = False, message: str) -> dict:
    return {
        "version": version,
        "cases": [
            {
                "id": "c1",
                "group": "red_flag" if red_flag else "llm",
                "message": message,
                "session_id": 1,
                "answer": ["请注意休息。"] if not red_flag else [],
            }
        ],
    }


def test_record_writes_a_versioned_baseline(tmp_path, capsys):
    cases_dir = tmp_path / "cases"
    baselines_dir = tmp_path / "baselines"
    _write_case_set(cases_dir, _case_set(message="我头疼"))

    code = regression_script.main(
        [
            "record",
            "--case-set",
            "t1",
            "--baseline-version",
            "t1",
            "--cases-dir",
            str(cases_dir),
            "--baselines-dir",
            str(baselines_dir),
        ]
    )

    assert code == 0
    written = json.loads((baselines_dir / "t1.json").read_text(encoding="utf-8"))
    assert written["case_set_version"] == "t1"
    assert written["cases"][0]["input"]["message"] == "我头疼"
    assert "t1" in capsys.readouterr().out


def test_replay_prints_metrics_and_writes_the_report(tmp_path, capsys):
    cases_dir = tmp_path / "cases"
    baselines_dir = tmp_path / "baselines"
    report_path = tmp_path / "report.json"
    _write_case_set(cases_dir, _case_set(message="我头疼"))
    regression_script.main(
        [
            "record",
            "--case-set",
            "t1",
            "--baseline-version",
            "t1",
            "--cases-dir",
            str(cases_dir),
            "--baselines-dir",
            str(baselines_dir),
        ]
    )
    capsys.readouterr()  # drop the record line so only the replay JSON remains

    code = regression_script.main(
        [
            "replay",
            "--case-set",
            "t1",
            "--baseline-version",
            "t1",
            "--cases-dir",
            str(cases_dir),
            "--baselines-dir",
            str(baselines_dir),
            "--report",
            str(report_path),
        ]
    )

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    # No red-flag cases in this fixture: nothing can be missed, so the rate is
    # vacuous 100% and the replay is not a blocking failure.
    assert printed["redflag_intercept_rate"] == 1.0
    assert set(printed["latency"]) == {"intercepted", "llm", "degraded"}
    assert json.loads(report_path.read_text(encoding="utf-8")) == printed


def test_replay_exits_nonzero_on_a_blocking_failure(tmp_path, capsys):
    cases_dir = tmp_path / "cases"
    baselines_dir = tmp_path / "baselines"
    # A red-flag case whose recorded decision is *not* intercept: a missed red flag.
    _write_case_set(
        cases_dir, _case_set(red_flag=True, message="今天感觉还不错，没有别的不舒服")
    )
    regression_script.main(
        [
            "record",
            "--case-set",
            "t1",
            "--baseline-version",
            "t1",
            "--cases-dir",
            str(cases_dir),
            "--baselines-dir",
            str(baselines_dir),
        ]
    )

    code = regression_script.main(
        [
            "replay",
            "--case-set",
            "t1",
            "--baseline-version",
            "t1",
            "--cases-dir",
            str(cases_dir),
            "--baselines-dir",
            str(baselines_dir),
        ]
    )

    assert code == 1
    assert "拦截率" in capsys.readouterr().err


def test_missing_case_set_exits_nonzero_with_a_message(tmp_path, capsys):
    code = regression_script.main(
        [
            "replay",
            "--case-set",
            "nope",
            "--baseline-version",
            "nope",
            "--cases-dir",
            str(tmp_path / "cases"),
            "--baselines-dir",
            str(tmp_path / "baselines"),
        ]
    )

    assert code == 1
    assert "nope" in capsys.readouterr().err


def test_replay_compare_prints_both_reports_and_the_delta(tmp_path, capsys):
    cases_dir = tmp_path / "cases"
    baselines_dir = tmp_path / "baselines"
    _write_case_set(cases_dir, _case_set(message="我头疼"))
    for version in ("t1", "t2"):
        regression_script.main(
            [
                "record",
                "--case-set",
                "t1",
                "--baseline-version",
                version,
                "--cases-dir",
                str(cases_dir),
                "--baselines-dir",
                str(baselines_dir),
            ]
        )
    capsys.readouterr()

    code = regression_script.main(
        [
            "replay",
            "--case-set",
            "t1",
            "--baseline-version",
            "t2",
            "--compare",
            "t1",
            "--cases-dir",
            str(cases_dir),
            "--baselines-dir",
            str(baselines_dir),
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["metrics"]["case_count"] == 1
    assert payload["compared_baseline_version"] == "t1"
    assert payload["delta"]["diagnosis_drift_rate"] == 0.0
    assert set(payload["delta"]["latency"]) == {"intercepted", "llm", "degraded"}


def test_replay_of_the_committed_baseline_succeeds(capsys):
    code = regression_script.main(
        ["replay", "--case-set", "v1", "--baseline-version", "v1"]
    )

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["redflag_intercept_rate"] == 1.0
    assert report["diagnosis_drift_rate"] == 0.0
