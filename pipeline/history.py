"""날짜별 누적 저장소.

GitHub Actions 러너는 매 실행마다 초기화됩니다. SQLite 를 커밋하면 바이너리 충돌이
나므로, **JSON 을 리포지토리의 단일 저장소로 두고 SQLite 는 매번 재구성**합니다.

    data/history/
      press_releases.jsonl     보도자료 누적 (매칭에 7일 소급이 필요하므로 유지)
      daily/<date>.json        그날의 분석 결과 (대시보드가 읽는 산출물)
      details/<date>/<id>.json 기사↔보도자료 문장 대조
      index.json               보유 날짜 목록
      outlets.json             날짜를 가로지르는 언론사별 집계

기사 본문은 저장하지 않습니다. 분석에만 필요하고, 저작권상 리포지토리에 쌓을 것이
아니며, 용량도 빠르게 불어납니다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")
HISTORY = Path(__file__).resolve().parents[1] / "data" / "history"
PR_FILE = HISTORY / "press_releases.jsonl"
DAILY_DIR = HISTORY / "daily"
DETAILS_DIR = HISTORY / "details"
INDEX_FILE = HISTORY / "index.json"


def snapshot_press_releases() -> int:
    """DB 의 보도자료를 jsonl 로 덤프합니다. url 기준 멱등."""
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM press_releases ORDER BY published_at, id"
    ).fetchall()
    conn.close()

    PR_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PR_FILE.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(dict(r), ensure_ascii=False) + "\n")
    return len(rows)


def restore_press_releases() -> int:
    """jsonl 을 SQLite 로 되살립니다. Actions 실행 첫 단계에서 호출합니다."""
    if not PR_FILE.exists():
        return 0
    conn = connect()
    n = 0
    with PR_FILE.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            conn.execute(
                """INSERT OR REPLACE INTO press_releases
                   (id, source_id, source_name, title, body, url, published_at, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (r["id"], r["source_id"], r["source_name"], r["title"], r["body"],
                 r["url"], r.get("published_at"), r["fetched_at"]),
            )
            n += 1
    conn.commit()
    conn.close()
    return n


def rebuild_index() -> list[str]:
    dates = sorted(p.stem for p in DAILY_DIR.glob("*.json")) if DAILY_DIR.exists() else []
    HISTORY.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(
        json.dumps({
            "dates": dates,
            "latest": dates[-1] if dates else None,
            "updatedAt": datetime.now(KST).isoformat(),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return dates


def prune_details(keep_days: int) -> int:
    """문장 대조 데이터는 용량이 크므로 최근 N일만 남깁니다.

    일별 집계(daily/*.json)는 계속 쌓아도 가볍지만, 문장 매핑은 기사 수에 비례해
    커집니다. 오래된 날짜의 대조 화면은 포기하고 통계만 남기는 편이 낫습니다.
    """
    if not DETAILS_DIR.exists():
        return 0
    dirs = sorted(d for d in DETAILS_DIR.iterdir() if d.is_dir())
    removed = 0
    for d in dirs[:-keep_days] if keep_days > 0 else []:
        for f in d.glob("*.json"):
            f.unlink()
        d.rmdir()
        removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="날짜별 누적 저장소 관리")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("restore", help="jsonl → SQLite (실행 전)")
    sub.add_parser("snapshot", help="SQLite → jsonl (실행 후)")
    sub.add_parser("index", help="보유 날짜 목록 재작성")
    p = sub.add_parser("prune", help="오래된 문장 대조 데이터 정리")
    p.add_argument("--keep-days", type=int, default=30)

    args = ap.parse_args()
    if args.cmd == "restore":
        print(f"보도자료 복원 {restore_press_releases()}건")
    elif args.cmd == "snapshot":
        print(f"보도자료 저장 {snapshot_press_releases()}건")
    elif args.cmd == "index":
        dates = rebuild_index()
        print(f"보유 날짜 {len(dates)}일" + (f" ({dates[0]} ~ {dates[-1]})" if dates else ""))
    elif args.cmd == "prune":
        print(f"오래된 대조 데이터 {prune_details(args.keep_days)}일치 삭제")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
