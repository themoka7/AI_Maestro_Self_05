"""Claude 기반 보도 프레이밍 분류 (Watchdog / Cheerleader / Neutral).

설계 결정 두 가지:
  1. Batch API 를 기본으로 씁니다. 하루 수백 건 분류는 동기 호출로 돌릴 이유가 없고
     배치가 비용이 절반입니다. --sync 는 소량 테스트/디버깅용입니다.
  2. 분류 프롬프트에 복제율을 넣지 않습니다. 복제율과 프레이밍은 독립 신호로 둬야
     "복제율이 높아서 홍보로 분류됐다"는 순환논증을 피할 수 있습니다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")
DEFAULT_MODEL = "claude-opus-5"
BODY_LIMIT = 4000

SYSTEM = """당신은 언론 보도의 자율성과 보도자료 의존도를 분석하는 미디어 연구자입니다.
정치적 입장이 아니라 취재 행위의 성격만 평가합니다. 기사에 담긴 주장의 옳고 그름,
특정 정당이나 인물에 대한 호오는 판단 대상이 아닙니다."""

TOOL = {
    "name": "classify_article",
    "description": "기사 한 건의 보도 프레이밍을 분류한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["Watchdog", "Cheerleader", "Neutral"],
                "description": (
                    "Watchdog: 공적 자금 집행을 따지거나, 문제점·예산 낭비·안전 부실·행정 태만을 "
                    "독자적으로 취재해 지적한 기사. 취재원이 복수이거나 자체 확인 과정이 드러남.\n"
                    "Cheerleader: 행사·정책을 비판 없이 홍보하고, 행정 발표를 그대로 옮기며, "
                    "독자적 검증 없이 구호·기대효과를 전달한 기사.\n"
                    "Neutral: 일정·교통통제·운영시간 등 단순 사실 고지. 홍보도 비판도 아닌 정보 전달."
                ),
            },
            "score": {
                "type": "number",
                "description": "-1.0(전형적 홍보) ~ 0(중립) ~ +1.0(철저한 감시 보도)",
            },
            "confidence": {
                "type": "number",
                "description": "0.0~1.0. 본문이 짧거나 판단이 모호하면 낮게.",
            },
            "rationale": {"type": "string", "description": "한국어 1~2문장 근거"},
            "flagged_issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "기사가 제기한 핵심 문제 제기 목록. 없으면 빈 배열.",
            },
        },
        "required": ["category", "score", "confidence", "rationale", "flagged_issues"],
    },
}


def build_prompt(title: str, outlet: str, body: str) -> str:
    return (
        f"다음 기사를 분류하세요.\n\n"
        f"제목: {title}\n언론사: {outlet}\n\n본문:\n{body[:BODY_LIMIT]}\n\n"
        f"classify_article 도구를 호출해 결과를 제출하세요."
    )


def request_params(model: str, row) -> dict:
    return {
        "model": model,
        "max_tokens": 1000,
        "temperature": 0,
        "system": SYSTEM,
        "tools": [TOOL],
        "tool_choice": {"type": "tool", "name": "classify_article"},
        "messages": [{"role": "user",
                      "content": build_prompt(row["title"], row["outlet"], row["body"])}],
    }


def save(conn, article_id: str, payload: dict, model: str) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO classifications
           (article_id, category, score, confidence, rationale, flagged_issues, model, classified_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (article_id, payload["category"], float(payload["score"]),
         float(payload.get("confidence", 0.0)), payload.get("rationale", ""),
         json.dumps(payload.get("flagged_issues", []), ensure_ascii=False),
         model, datetime.now(KST).isoformat()),
    )


def pending_rows(conn, date: str, limit: int, recheck: bool):
    where = "" if recheck else "AND c.article_id IS NULL"
    rows = conn.execute(
        f"""SELECT a.id, a.title, a.outlet, a.body FROM articles a
            LEFT JOIN classifications c ON c.article_id = a.id
            WHERE a.target_date = ? AND a.body_status = 'ok' {where}
            ORDER BY a.published_at""",
        (date,),
    ).fetchall()
    return rows[:limit] if limit else rows


def run_sync(client, conn, rows, model: str) -> None:
    for i, row in enumerate(rows, 1):
        msg = client.messages.create(**request_params(model, row))
        block = next((b for b in msg.content if b.type == "tool_use"), None)
        if block is None:
            print(f"  [{row['id']}] 도구 호출 없음 — 건너뜀", file=sys.stderr)
            continue
        save(conn, row["id"], block.input, model)
        if i % 10 == 0:
            conn.commit()
            print(f"  {i}/{len(rows)} ...", flush=True)
    conn.commit()


def run_batch(client, conn, rows, model: str, poll: int, max_wait: int = 0) -> None:
    batch = client.messages.batches.create(
        requests=[{"custom_id": r["id"], "params": request_params(model, r)} for r in rows]
    )
    print(f"  배치 생성: {batch.id} ({len(rows)}건). 폴링 간격 {poll}초"
          + (f", 최대 대기 {max_wait}초" if max_wait else ""))
    started = time.monotonic()
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        print(f"  {batch.processing_status} "
              f"성공={counts.succeeded} 오류={counts.errored} 취소={counts.canceled} "
              f"만료={counts.expired}", flush=True)
        if batch.processing_status == "ended":
            break
        if max_wait and time.monotonic() - started > max_wait:
            # 배치는 서버에 그대로 남아 있습니다. 결과를 못 받았을 뿐이라
            # 같은 날짜로 다시 돌리면 미분류 기사만 다시 제출됩니다.
            raise TimeoutError(
                f"배치 {batch.id} 가 {max_wait}초 안에 끝나지 않았습니다. "
                f"같은 날짜로 재실행하세요 (이미 분류된 기사는 건너뜁니다)."
            )
        time.sleep(poll)

    ok = failed = 0
    for result in client.messages.batches.results(batch.id):
        if result.result.type != "succeeded":
            failed += 1
            print(f"  [{result.custom_id}] {result.result.type}", file=sys.stderr)
            continue
        block = next((b for b in result.result.message.content if b.type == "tool_use"), None)
        if block is None:
            failed += 1
            continue
        save(conn, result.custom_id, block.input, model)
        ok += 1
    conn.commit()
    print(f"  저장 완료: 성공 {ok}건, 실패 {failed}건")


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Claude 로 기사 프레이밍 분류")
    ap.add_argument("--date", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sync", action="store_true", help="배치 대신 동기 호출 (소량 테스트용)")
    ap.add_argument("--recheck", action="store_true", help="이미 분류된 기사도 다시 분류")
    ap.add_argument("--poll", type=int, default=30, help="배치 상태 폴링 간격(초)")
    ap.add_argument("--allow-missing-key", action="store_true",
                    help="ANTHROPIC_API_KEY 가 없으면 실패 대신 건너뜁니다. "
                         "분류만 빠지고 복제율 지표는 그대로 산출됩니다.")
    ap.add_argument("--max-wait", type=int, default=0,
                    help="배치 최대 대기 시간(초). 0=무제한. CI 에서는 반드시 지정하세요.")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # 분류는 전체 파이프라인에서 선택적인 단계입니다. 키가 없다고 여기서 죽으면
        # 이미 수집한 기사와 이미 지불한 검색 API 호출까지 통째로 버려집니다.
        msg = "ANTHROPIC_API_KEY 가 없어 프레이밍 분류를 건너뜁니다. 복제율 지표는 그대로 산출됩니다."
        if args.allow_missing_key:
            print(f"⚠ {msg}", file=sys.stderr)
            return 0
        print(f"{msg}\n(파이프라인에서 계속 진행하려면 --allow-missing-key)", file=sys.stderr)
        return 2

    from anthropic import Anthropic

    model = os.environ.get("CLASSIFIER_MODEL", DEFAULT_MODEL)
    conn = connect()
    rows = pending_rows(conn, args.date, args.limit, args.recheck)
    if not rows:
        print("분류할 기사가 없습니다.")
        return 0

    print(f"{args.date}: {len(rows)}건 분류 (model={model}, "
          f"mode={'sync' if args.sync else 'batch'})")
    client = Anthropic()
    if args.sync:
        run_sync(client, conn, rows, model)
    else:
        try:
            run_batch(client, conn, rows, model, args.poll, args.max_wait)
        except TimeoutError as e:
            print(f"분류 미완료: {e}", file=sys.stderr)
            conn.close()
            return 3

    for r in conn.execute(
        """SELECT c.category, COUNT(*) n FROM classifications c
           JOIN articles a ON a.id = c.article_id
           WHERE a.target_date = ? GROUP BY c.category ORDER BY n DESC""",
        (args.date,),
    ):
        print(f"  {r['category']:<12} {r['n']}건")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
