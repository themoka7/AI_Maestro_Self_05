"""도메인 → 언론사명 매핑.

네이버 검색 API 응답에는 언론사 필드가 없습니다. originallink 도메인에서 역산해야 하고,
이게 이 파이프라인에서 가장 손이 많이 가는 부분입니다.

- 아래 표에 없는 도메인은 도메인 문자열을 그대로 언론사명으로 쓰고 resolved=False 로 표시합니다.
  (랭킹에서 제외하지 않고 "미확인"으로 노출해, 매핑 누락이 조용히 통계를 왜곡하지 않게 합니다.)
- config/outlets_override.csv (domain,name) 파일로 얼마든지 덧붙일 수 있습니다.
"""
from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import urlsplit

OVERRIDE_PATH = Path(__file__).resolve().parents[2] / "config" / "outlets_override.csv"

# 전국지 · 통신사 · 방송 · 경제지
NATIONAL = {
    "yna.co.kr": "연합뉴스",
    "yonhapnewstv.co.kr": "연합뉴스TV",
    "newsis.com": "뉴시스",
    "news1.kr": "뉴스1",
    "chosun.com": "조선일보",
    "donga.com": "동아일보",
    "joongang.co.kr": "중앙일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "hankookilbo.com": "한국일보",
    "seoul.co.kr": "서울신문",
    "segye.com": "세계일보",
    "munhwa.com": "문화일보",
    "kmib.co.kr": "국민일보",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "sedaily.com": "서울경제",
    "fnnews.com": "파이낸셜뉴스",
    "asiae.co.kr": "아시아경제",
    "edaily.co.kr": "이데일리",
    "mt.co.kr": "머니투데이",
    "heraldcorp.com": "헤럴드경제",
    "etnews.com": "전자신문",
    "kbs.co.kr": "KBS",
    "imnews.imbc.com": "MBC",
    "sbs.co.kr": "SBS",
    "ytn.co.kr": "YTN",
    "jtbc.co.kr": "JTBC",
    "news.kbs.co.kr": "KBS",
    "ohmynews.com": "오마이뉴스",
    "pressian.com": "프레시안",
    "nocutnews.co.kr": "노컷뉴스",
    "mediatoday.co.kr": "미디어오늘",
    "newstapa.org": "뉴스타파",
}

# 전남 · 광주 권역 지역지 (여수 이슈 커버리지의 핵심)
LOCAL_JEONNAM = {
    "jnilbo.com": "전남일보",
    "namdonews.com": "남도일보",
    "kwangju.co.kr": "광주일보",
    "honam.co.kr": "호남매일",
    "jndn.com": "전남매일",
    "gjdream.com": "광주드림",
    "jeonmae.co.kr": "전남매일신문",
    "yeosunews.co.kr": "여수신문",
    "ysmbc.co.kr": "여수MBC",
}

DOMAIN_MAP: dict[str, str] = {**NATIONAL, **LOCAL_JEONNAM}

# 네이버 뉴스 재배포 도메인 — originallink 가 비었을 때만 등장하며, 언론사 특정 불가
NAVER_DOMAINS = {"n.news.naver.com", "news.naver.com", "m.news.naver.com"}

_override_cache: dict[str, str] | None = None


def _overrides() -> dict[str, str]:
    global _override_cache
    if _override_cache is None:
        _override_cache = {}
        if OVERRIDE_PATH.exists():
            with OVERRIDE_PATH.open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    d = (row.get("domain") or "").strip().lower()
                    n = (row.get("name") or "").strip()
                    if d and n:
                        _override_cache[d] = n
    return _override_cache


def registrable_domain(url: str) -> str:
    """서브도메인을 벗겨 등록 가능 도메인까지 줄입니다 (news.chosun.com → chosun.com)."""
    host = (urlsplit(url).hostname or "").lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return ""
    parts = host.split(".")
    # co.kr / or.kr / go.kr 처럼 2단계 suffix 는 3개까지 남깁니다.
    if len(parts) >= 3 and parts[-1] == "kr" and parts[-2] in {"co", "or", "go", "ne", "re", "pe"}:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def resolve(url: str) -> tuple[str, str, bool]:
    """(언론사명, 도메인, 매핑확인여부) 를 돌려줍니다."""
    host = (urlsplit(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in NAVER_DOMAINS:
        return ("네이버뉴스(원문미상)", host, False)

    ov = _overrides()
    for candidate in (host, registrable_domain(url)):
        if not candidate:
            continue
        if candidate in ov:
            return (ov[candidate], candidate, True)
        if candidate in DOMAIN_MAP:
            return (DOMAIN_MAP[candidate], candidate, True)

    domain = registrable_domain(url) or host or "unknown"
    return (domain, domain, False)


if __name__ == "__main__":
    for u in [
        "https://www.yna.co.kr/view/AKR20260915",
        "http://news.chosun.com/site/data/html_dir/a.html",
        "https://www.jnilbo.com/78325",
        "https://n.news.naver.com/mnews/article/001/0001",
        "https://www.nobody-knows-this.kr/news/1",
    ]:
        print(f"{u}\n  -> {resolve(u)}")
