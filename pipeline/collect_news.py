"""네이버 뉴스 검색 API 수집기.

API 제약 (설계에 직접 영향을 주는 것들):
  * 기간 필터 파라미터가 없습니다. sort=date 로 최신순 페이징하며 대상 날짜를 지나면 끊습니다.
  * start 는 최대 1000, display 는 최대 100 → 쿼리 1건당 최대 1,000건까지만 접근 가능합니다.
    따라서 커버리지는 config/event.yaml 의 queries 를 여러 개로 쪼개서 확보합니다.
  * 언론사 필드가 없습니다 → originallink 도메인에서 역산합니다 (sources/outlets.py).
  * 본문이 없습니다 (title/description 만) → extract_body.py 에서 원문을 따로 가져옵니다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402
from nlp import clean_text  # noqa: E402
from sources.outlets import resolve as resolve_outlet  # noqa: E402

API_URL = "https://openapi.naver.com/v1/search/news.json"
KST = timezone(timedelta(hours=9), "KST")
MAX_START = 1000
DISPLAY = 100

# 본문 식별에 무관한 추적 파라미터만 제거합니다.
# (한국 언론사 URL 은 ?idxno=123 처럼 쿼리에 기사 ID 가 들어있는 경우가 많아 전부 지우면 안 됩니다.)
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "from", "ref", "cmpid", "sc_from",
}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if k.lower() not in TRACKING_PARAMS])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme or "https", host, path, query, ""))


def canonical_key(url: str) -> str:
    """동일성 판정용 키. http/https 차이로 같은 기사가 두 건으로 세지는 걸 막습니다."""
    return normalize_url(url).split("://", 1)[-1]


def article_id(url: str) -> str:
    return hashlib.sha1(canonical_key(url).encode()).hexdigest()[:16]


def yesterday_kst() -> str:
    return (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d")


def search(session: requests.Session, query: str, start: int) -> dict:
    resp = session.get(
        API_URL,
        params={"query": query, "display": DISPLAY, "start": start, "sort": "date"},
        timeout=15,
    )
    if resp.status_code == 429:
        raise RuntimeError("네이버 API 호출 한도 초과 (검색 API 일 25,000건)")
    resp.raise_for_status()
    return resp.json()


def collect_query(session: requests.Session, query: str, target_date: str) -> list[dict]:
    """대상 날짜(KST) 하루치 기사만 뽑아냅니다."""
    day_start = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=KST)
    day_end = day_start + timedelta(days=1)

    found: list[dict] = []
    start = 1
    while start <= MAX_START:
        data = search(session, query, start)
        items = data.get("items", [])
        if not items:
            break

        passed_window = False
        for item in items:
            raw = item.get("originallink") or item.get("link") or ""
            if not raw:
                continue
            try:
                published = parsedate_to_datetime(item["pubDate"]).astimezone(KST)
            except (KeyError, TypeError, ValueError):
                continue

            if published >= day_end:
                continue                      # 아직 대상 날짜보다 미래 (최신순이라 앞부분)
            if published < day_start:
                passed_window = True          # 대상 날짜를 지나 과거로 넘어감 → 중단
                break

            outlet, domain, resolved = resolve_outlet(raw)
            found.append({
                "id": article_id(raw),
                "title": clean_text(item.get("title")),
                "description": clean_text(item.get("description")),
                "url": normalize_url(raw),
                "naver_url": item.get("link") or None,
                "outlet": outlet,
                "outlet_domain": domain,
                "outlet_resolved": resolved,
                "published_at": published.isoformat(),
                "target_date": target_date,
                "query": query,
            })

        if passed_window or len(items) < DISPLAY:
            break
        start += DISPLAY
        time.sleep(0.1)                       # 예의상 간격
    return found


def upsert(conn, rows: list[dict]) -> tuple[int, int]:
    """멱등 삽입. 같은 날 여러 번 돌려도 중복이 쌓이지 않고, 검색어만 병합됩니다."""
    now = datetime.now(KST).isoformat()
    inserted = merged = 0
    for r in rows:
        existing = conn.execute(
            "SELECT queries FROM articles WHERE id = ?", (r["id"],)
        ).fetchone()
        if existing:
            queries = set(json.loads(existing["queries"]))
            if r["query"] not in queries:
                queries.add(r["query"])
                conn.execute("UPDATE articles SET queries = ? WHERE id = ?",
                             (json.dumps(sorted(queries), ensure_ascii=False), r["id"]))
            merged += 1
            continue
        conn.execute(
            """INSERT INTO articles
               (id, title, description, url, naver_url, outlet, outlet_domain,
                published_at, target_date, queries, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (r["id"], r["title"], r["description"], r["url"], r["naver_url"],
             r["outlet"], r["outlet_domain"], r["published_at"], r["target_date"],
             json.dumps([r["query"]], ensure_ascii=False), now),
        )
        inserted += 1
    conn.commit()
    return inserted, merged


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="네이버 뉴스 검색 API로 하루치 기사 수집")
    ap.add_argument("--date", default=None, help="대상 날짜 YYYY-MM-DD (기본: 어제, KST)")
    ap.add_argument("--config", default="config/event.yaml")
    args = ap.parse_args()

    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 없습니다. .env 를 확인하세요.",
              file=sys.stderr)
        return 2

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    target_date = args.date or yesterday_kst()

    session = requests.Session()
    session.headers.update({
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    })

    conn = connect()
    total_new = total_merged = 0
    for query in cfg["queries"]:
        rows = collect_query(session, query, target_date)
        new, merged = upsert(conn, rows)
        total_new += new
        total_merged += merged
        print(f"  [{query}] 수집 {len(rows)}건 → 신규 {new}, 기존 {merged}")

    unresolved = conn.execute(
        """SELECT outlet_domain, COUNT(*) c FROM articles
           WHERE target_date = ? AND outlet = outlet_domain
           GROUP BY outlet_domain ORDER BY c DESC LIMIT 10""",
        (target_date,),
    ).fetchall()
    print(f"\n{target_date}: 신규 {total_new}건, 중복 병합 {total_merged}건")
    if unresolved:
        print("언론사 매핑 누락 도메인 (config/outlets_override.csv 에 추가 권장):")
        for row in unresolved:
            print(f"  {row['outlet_domain']}  {row['c']}건")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
