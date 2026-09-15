"""보도자료 게시판 구조를 훑어 CSS 선택자 후보를 뽑아냅니다.

config/event.yaml 의 press_release_sources 선택자는 게시판 실물을 봐야 정해집니다.
지자체 홈페이지는 구조가 제각각이라 추측으로는 맞지 않습니다.

    python scripts/inspect_board.py "https://www.example.go.kr/board/list"

출력한 후보를 config/event.yaml 에 넣고 enabled: true 로 바꾼 뒤
`python pipeline/collect_pr.py --source <id>` 로 확인하세요.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

UA = "ParallaxBot/0.1 (board structure inspection; +contact in repo README)"
DATE_RE = re.compile(r"\d{4}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}")


def describe(el) -> str:
    """요소를 CSS 선택자 비슷하게 표현합니다."""
    parts = [el.name]
    if el.get("id"):
        return f"{el.name}#{el['id']}"
    for cls in (el.get("class") or [])[:2]:
        parts.append(f".{cls}")
    return "".join(parts)


def path_of(el, depth: int = 4) -> str:
    chain, cur = [], el
    while cur is not None and cur.name != "[document]" and len(chain) < depth:
        chain.append(describe(cur))
        cur = cur.parent
    return " > ".join(reversed(chain))


def main() -> int:
    ap = argparse.ArgumentParser(description="게시판 선택자 후보 추출")
    ap.add_argument("url")
    ap.add_argument("--detail", help="상세 페이지 URL (본문 선택자 후보를 함께 뽑음)")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})

    try:
        resp = session.get(args.url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"가져오지 못했습니다: {e}", file=sys.stderr)
        return 1
    resp.encoding = resp.apparent_encoding or resp.encoding
    soup = BeautifulSoup(resp.text, "lxml")

    print(f"=== {args.url} ({len(resp.text):,} bytes) ===\n")

    # 목록 행 후보: 링크를 담은 반복 구조를 찾습니다.
    containers = Counter()
    for a in soup.find_all("a", href=True):
        if not a.get_text(strip=True):
            continue
        for parent in list(a.parents)[:3]:
            if parent.name in ("tr", "li", "dl", "div"):
                containers[path_of(parent, 3)] += 1
                break

    print("[목록 행(row) 후보] — 반복 횟수가 게시글 수와 비슷한 것을 고르세요")
    for path, n in containers.most_common(8):
        print(f"  {n:>4}회  {path}")

    # 날짜가 든 셀 → date 선택자 힌트
    dated = Counter()
    for el in soup.find_all(["td", "span", "div", "p"]):
        text = el.get_text(" ", strip=True)
        if len(text) < 30 and DATE_RE.search(text):
            dated[describe(el)] += 1
    if dated:
        print("\n[날짜(date) 후보]")
        for path, n in dated.most_common(5):
            print(f"  {n:>4}회  {path}")

    # 첫 번째 게시글 링크 → 상세 페이지 URL 예시
    links = [a for a in soup.find_all("a", href=True)
             if len(a.get_text(strip=True)) > 8 and "javascript" not in a["href"].lower()]
    if links:
        print("\n[게시글 링크 예시]")
        for a in links[:3]:
            print(f"  {a.get_text(strip=True)[:40]}")
            print(f"    → {urljoin(resp.url, a['href'])}")

    if not args.detail:
        print("\n상세 페이지 본문 선택자를 보려면 위 링크 하나를 --detail 로 넘기세요.")
        return 0

    # 상세 페이지: 가장 긴 텍스트 블록이 대개 본문입니다.
    d = session.get(args.detail, timeout=20)
    d.encoding = d.apparent_encoding or d.encoding
    dsoup = BeautifulSoup(d.text, "lxml")
    for tag in dsoup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    blocks = []
    for el in dsoup.find_all(["div", "article", "section", "td"]):
        text = el.get_text(" ", strip=True)
        # 자식이 아니라 자신이 본문을 담은 블록을 고르기 위해 직계 텍스트 비중을 봅니다.
        if len(text) > 200:
            blocks.append((len(text), describe(el), text[:80]))
    blocks.sort(reverse=True)

    print(f"\n=== 상세: {args.detail} ===")
    print("[본문(detail_body) 후보] — 글자 수가 많고 선택자가 구체적인 것")
    for length, sel, preview in blocks[:6]:
        print(f"  {length:>6}자  {sel}")
        print(f"          {preview}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
