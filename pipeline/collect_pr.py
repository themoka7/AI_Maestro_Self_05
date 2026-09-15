"""보도자료 수집.

두 가지 경로를 지원합니다.
  1) --source <id> : config/event.yaml 의 CSS 선택자로 게시판을 긁습니다.
     지자체 게시판은 구조가 제각각이라 선택자는 실물을 보고 맞춰야 합니다.
     scripts/inspect_board.py 로 후보 선택자를 뽑아볼 수 있습니다.
  2) --import <file> : JSON/JSONL 을 직접 밀어 넣습니다.
     게시판이 JS 렌더링이거나 본문이 hwp/pdf 첨부에만 있는 경우의 탈출구입니다.
     (지자체 보도자료는 본문이 첨부파일에만 있는 경우가 실제로 꽤 됩니다.)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402
from nlp import clean_text  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")
USER_AGENT = "MediaWatchBot/0.1 (media fairness research; +contact in repo README)"
DATE_RE = re.compile(r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})")


def pr_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def parse_date(text: str | None) -> str | None:
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    try:
        return datetime(y, mo, d, tzinfo=KST).date().isoformat()
    except ValueError:
        return None


def upsert(conn, rows: list[dict]) -> int:
    now = datetime.now(KST).isoformat()
    new = 0
    for r in rows:
        if not r.get("url") or not r.get("title"):
            continue
        cur = conn.execute(
            """INSERT INTO press_releases
               (id, source_id, source_name, title, body, url, published_at, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET
                   title = excluded.title,
                   body = CASE WHEN excluded.body != '' THEN excluded.body ELSE press_releases.body END,
                   published_at = COALESCE(excluded.published_at, press_releases.published_at)""",
            (pr_id(r["url"]), r.get("source_id", "manual"), r.get("source_name", "수동 입력"),
             clean_text(r["title"]), clean_text(r.get("body", "")), r["url"],
             r.get("published_at"), now),
        )
        new += cur.rowcount
    conn.commit()
    return new


def scrape_source(cfg_source: dict) -> list[dict]:
    sel = cfg_source["selectors"]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    rows: list[dict] = []
    for page in range(1, int(cfg_source.get("max_pages", 1)) + 1):
        params = {k: v.replace("{page}", str(page))
                  for k, v in (cfg_source.get("list_params") or {}).items()}
        resp = session.get(cfg_source["list_url"], params=params, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        soup = BeautifulSoup(resp.text, "lxml")

        entries = soup.select(sel["row"])
        if not entries:
            print(f"  page {page}: 행 선택자 '{sel['row']}' 가 아무것도 못 잡았습니다. "
                  f"선택자를 다시 확인하세요.", file=sys.stderr)
            break

        for entry in entries:
            link = entry.select_one(sel["link"])
            if not link or not link.get("href"):
                continue
            detail_url = urljoin(resp.url, link["href"])
            date_el = entry.select_one(sel["date"]) if sel.get("date") else None
            rows.append({
                "url": detail_url,
                "title": clean_text(link.get_text()),
                "published_at": parse_date(date_el.get_text() if date_el else None),
                "source_id": cfg_source["id"],
                "source_name": cfg_source["name"],
            })
        time.sleep(1.0)

    # 상세 페이지에서 본문을 채웁니다.
    for row in rows:
        try:
            time.sleep(1.0)
            d = session.get(row["url"], timeout=20)
            d.encoding = d.apparent_encoding or d.encoding
            dsoup = BeautifulSoup(d.text, "lxml")
            body_el = dsoup.select_one(sel["detail_body"])
            row["body"] = clean_text(body_el.get_text(" ")) if body_el else ""
            if not row["published_at"] and sel.get("detail_date"):
                dt_el = dsoup.select_one(sel["detail_date"])
                row["published_at"] = parse_date(dt_el.get_text() if dt_el else None)
        except requests.RequestException as e:
            print(f"  본문 실패 {row['url']}: {e}", file=sys.stderr)
            row["body"] = ""
    return rows


def load_import(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    return data if isinstance(data, list) else data.get("press_releases", [])


def main() -> int:
    ap = argparse.ArgumentParser(description="보도자료 수집")
    ap.add_argument("--config", default="config/event.yaml")
    ap.add_argument("--source", help="config 의 press_release_sources.id")
    ap.add_argument("--import", dest="import_path", help="JSON/JSONL 직접 임포트")
    args = ap.parse_args()

    conn = connect()
    if args.import_path:
        rows = load_import(Path(args.import_path))
        print(f"임포트 {len(rows)}건 → 신규 {upsert(conn, rows)}건")
        conn.close()
        return 0

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    sources = cfg.get("press_release_sources", [])
    targets = [s for s in sources
               if (args.source and s["id"] == args.source) or (not args.source and s.get("enabled"))]
    if not targets:
        print("활성화된 보도자료 소스가 없습니다. "
              "config/event.yaml 에서 enabled: true 로 바꾸거나 --import 를 쓰세요.")
        conn.close()
        return 1

    for src in targets:
        print(f"[{src['name']}] 수집 중...")
        rows = scrape_source(src)
        with_body = sum(1 for r in rows if r.get("body"))
        print(f"  목록 {len(rows)}건, 본문 확보 {with_body}건 → 신규 {upsert(conn, rows)}건")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
