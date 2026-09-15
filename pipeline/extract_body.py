"""기사 원문 본문 추출.

네이버 검색 API는 본문을 주지 않습니다(제목 + 요약 200자 내외). 복제율 계산은 본문 없이는
성립하지 않으므로 originallink 를 직접 받아와 본문을 뽑습니다.

수집 예절 — 이걸 지키지 않으면 금방 차단당합니다:
  * robots.txt 를 확인하고 금지된 경로는 건너뜁니다 (body_status='blocked').
  * 도메인별 최소 요청 간격을 둡니다.
  * 식별 가능한 User-Agent 를 씁니다.
본문 저작권상 원문 전체를 외부에 재공개하면 안 됩니다. DB에는 분석용으로만 보관하고,
대시보드에는 매칭된 문장 단위 인용만 노출하도록 export.py 에서 잘라냅니다.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
import trafilatura

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402
from nlp import clean_text  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")
USER_AGENT = "MediaWatchBot/0.1 (media fairness research; +contact in repo README)"
MIN_BODY_CHARS = 200
PER_DOMAIN_DELAY = 1.5

_robots: dict[str, RobotFileParser | None] = {}
_last_hit: dict[str, float] = defaultdict(float)


def robots_allows(session: requests.Session, url: str) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots:
        rp = RobotFileParser()
        try:
            resp = session.get(f"{origin}/robots.txt", timeout=10)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp = None          # robots.txt 없음 → 허용으로 간주
        except requests.RequestException:
            rp = None
        _robots[origin] = rp
    rp = _robots[origin]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def throttle(url: str) -> None:
    host = urlsplit(url).netloc
    elapsed = time.monotonic() - _last_hit[host]
    if elapsed < PER_DOMAIN_DELAY:
        time.sleep(PER_DOMAIN_DELAY - elapsed)
    _last_hit[host] = time.monotonic()


def extract(session: requests.Session, url: str) -> tuple[str, str, str | None]:
    """(본문, 상태, 에러) 반환."""
    if not robots_allows(session, url):
        return "", "blocked", "robots.txt disallow"
    throttle(url)
    try:
        resp = session.get(url, timeout=20, allow_redirects=True)
    except requests.RequestException as e:
        return "", "failed", f"{type(e).__name__}: {e}"
    if resp.status_code >= 400:
        return "", "failed", f"HTTP {resp.status_code}"

    resp.encoding = resp.apparent_encoding or resp.encoding
    body = trafilatura.extract(
        resp.text,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        url=url,
    ) or ""
    body = clean_text(body)
    if len(body) < MIN_BODY_CHARS:
        return body, "empty", f"본문 {len(body)}자 (임계 {MIN_BODY_CHARS}자 미만)"
    return body, "ok", None


def main() -> int:
    ap = argparse.ArgumentParser(description="기사 원문 본문 수집")
    ap.add_argument("--date", required=True, help="대상 날짜 YYYY-MM-DD")
    ap.add_argument("--limit", type=int, default=0, help="0이면 전체")
    ap.add_argument("--retry-failed", action="store_true", help="이전에 실패한 건도 재시도")
    args = ap.parse_args()

    statuses = ("pending",) if not args.retry_failed else ("pending", "failed", "empty")
    conn = connect()
    rows = conn.execute(
        f"""SELECT id, url, naver_url FROM articles
            WHERE target_date = ? AND body_status IN ({','.join('?' * len(statuses))})
            ORDER BY published_at""",
        (args.date, *statuses),
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"})

    tally: dict[str, int] = defaultdict(int)
    for i, row in enumerate(rows, 1):
        body, status, err = extract(session, row["url"])
        # 원문 추출에 실패하면 네이버 재배포 링크로 한 번 더 시도합니다.
        if status != "ok" and row["naver_url"] and row["naver_url"] != row["url"]:
            body2, status2, err2 = extract(session, row["naver_url"])
            if status2 == "ok":
                body, status, err = body2, status2, err2

        conn.execute(
            "UPDATE articles SET body = ?, body_status = ?, body_error = ?, fetched_at = ? WHERE id = ?",
            (body, status, err, datetime.now(KST).isoformat(), row["id"]),
        )
        tally[status] += 1
        if i % 20 == 0:
            conn.commit()
            print(f"  {i}/{len(rows)} ...", flush=True)
    conn.commit()

    print(f"\n본문 추출 {len(rows)}건: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    if tally["blocked"] or tally["failed"]:
        print("실패 도메인 상위:")
        for r in conn.execute(
            """SELECT outlet, body_status, COUNT(*) c FROM articles
               WHERE target_date = ? AND body_status IN ('blocked','failed','empty')
               GROUP BY outlet, body_status ORDER BY c DESC LIMIT 10""",
            (args.date,),
        ):
            print(f"  {r['outlet']:<16} {r['body_status']:<8} {r['c']}건")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
