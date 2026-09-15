"""파이프라인 오케스트레이터. 기본 동작은 "어제 하루치" 전체 처리입니다.

    python pipeline/run.py                      # 어제(KST) 전체 단계
    python pipeline/run.py --date 2026-09-14    # 특정 날짜
    python pipeline/run.py --skip classify      # 특정 단계 건너뛰기
    python pipeline/run.py --only match score export

각 단계는 멱등합니다. 같은 날 여러 번 돌려도 기사가 중복으로 쌓이지 않고,
이미 본문을 받아온 기사는 다시 받지 않으며, 이미 분류된 기사는 다시 분류하지 않습니다.
(재처리가 필요하면 각 단계의 --retry-failed / --recheck 를 쓰세요.)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")
ROOT = Path(__file__).resolve().parents[1]
PY_BIN = sys.executable

STAGES = ["collect_pr", "collect_news", "extract_body", "dedup", "match", "classify", "export"]
# 날짜 인자를 받지 않는 단계
NO_DATE = {"collect_pr"}


def stage_cmd(stage: str, date: str) -> list[str]:
    script = ROOT / "pipeline" / f"{stage}.py"
    cmd = [PY_BIN, str(script)]
    if stage == "collect_news":
        cmd += ["--date", date]
    elif stage not in NO_DATE:
        cmd += ["--date", date]
    return cmd


def record(conn, date: str, stage: str, started: str, ok: bool, err: str | None) -> None:
    conn.execute(
        "INSERT INTO runs (target_date, stage, started_at, finished_at, stats, error) "
        "VALUES (?,?,?,?,?,?)",
        (date, stage, started, datetime.now(KST).isoformat(),
         json.dumps({"ok": ok}), err),
    )
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description="Parallax 파이프라인 실행")
    ap.add_argument("--date", default=None, help="기본: 어제 (KST)")
    ap.add_argument("--only", nargs="+", choices=STAGES, help="이 단계들만 실행")
    ap.add_argument("--skip", nargs="+", choices=STAGES, default=[], help="건너뛸 단계")
    ap.add_argument("--continue-on-error", action="store_true",
                    help="단계 실패해도 다음 단계 진행")
    args = ap.parse_args()

    date = args.date or (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d")
    stages = args.only or [s for s in STAGES if s not in args.skip]

    conn = connect()
    print(f"═══ Parallax 파이프라인 | 대상일 {date} ═══")
    failures = []
    for stage in stages:
        started = datetime.now(KST).isoformat()
        print(f"\n▶ {stage}")
        proc = subprocess.run(stage_cmd(stage, date), cwd=ROOT)
        ok = proc.returncode == 0
        record(conn, date, stage, started, ok, None if ok else f"exit {proc.returncode}")
        if not ok:
            failures.append(stage)
            print(f"  ✗ {stage} 실패 (exit {proc.returncode})", file=sys.stderr)
            if not args.continue_on_error:
                conn.close()
                return proc.returncode

    print(f"\n═══ 완료 | 성공 {len(stages) - len(failures)}/{len(stages)} ═══")
    if failures:
        print(f"실패 단계: {', '.join(failures)}", file=sys.stderr)
    conn.close()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
