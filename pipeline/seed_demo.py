"""데모 데이터 시드 — API 키 없이 파이프라인 전체를 돌려보기 위한 것.

주의: 여기서 만드는 기사/보도자료/분류는 전부 합성 데이터입니다. 실제 보도가 아닙니다.
언론사명은 매핑 동작 확인용으로 쓰였을 뿐, 어떤 실제 매체의 보도 행태도 나타내지 않습니다.
분류 결과도 Claude 가 아니라 규칙 기반 목(mock)이며 model 필드에 'mock' 으로 남깁니다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")

PRESS_RELEASES = [
    {
        "key": "budget",
        "title": "여수시, 2026 세계섬박람회 총사업비 2,300억원 투입 확정",
        "body": (
            "여수시는 2026 여수세계섬박람회의 성공적인 개최를 위해 총사업비 2,300억원을 투입한다고 밝혔다. "
            "박람회는 2026년 8월 1일부터 9월 30일까지 61일간 여수세계박람회장 일원에서 개최된다. "
            "시는 국비 920억원, 도비 460억원, 시비 920억원을 확보해 전시관 조성과 기반시설 정비에 집중한다. "
            "주요 사업으로는 섬 주제관 건립, 해상 이동 동선 확충, 관람객 편의시설 확충이 포함된다. "
            "시는 이번 박람회를 통해 관람객 350만명을 유치하고 생산유발효과 1조 2천억원을 기대하고 있다. "
            "여수시 관계자는 남해안 섬 관광의 새로운 전기를 마련하겠다고 말했다."
        ),
    },
    {
        "key": "safety",
        "title": "박람회 조직위, 해상 안전관리 종합대책 수립",
        "body": (
            "2026 여수세계섬박람회 조직위원회는 해상 관람객 안전관리 종합대책을 수립했다고 밝혔다. "
            "조직위는 박람회 기간 중 운항하는 여객선 18척에 대해 사전 안전점검을 실시한다. "
            "해양경찰서와 협력해 상시 순찰 체계를 운영하고 응급 의료 이송 체계를 구축한다. "
            "관람객 밀집이 예상되는 선착장 6곳에는 안전 요원을 상시 배치할 계획이다. "
            "조직위 관계자는 안전이 최우선 가치라며 빈틈없는 준비를 약속했다."
        ),
    },
    {
        "key": "schedule",
        "title": "박람회장 주변 교통통제 및 셔틀버스 운행 안내",
        "body": (
            "여수시는 박람회 기간 중 박람회장 주변 도로의 교통을 통제한다고 안내했다. "
            "통제 구간은 박람회장 진입로 2.4킬로미터 구간이며 통제 시간은 오전 8시부터 오후 10시까지다. "
            "셔틀버스는 여수엑스포역과 여수종합버스터미널에서 15분 간격으로 운행한다. "
            "자가용 이용 관람객은 임시 주차장 4곳을 이용할 수 있다."
        ),
    },
]

# (언론사, 도메인, [기사유형...]) — 유형별로 매체 성향을 다르게 구성
OUTLETS = [
    ("연합뉴스",   "yna.co.kr",       ["verbatim:budget", "verbatim:safety", "neutral:schedule"]),
    ("전남일보",   "jnilbo.com",      ["verbatim:budget", "critical:budget", "neutral:schedule"]),
    ("광주일보",   "kwangju.co.kr",   ["verbatim:budget", "verbatim:safety"]),
    ("남도일보",   "namdonews.com",   ["verbatim:safety", "verbatim:schedule", "verbatim:budget"]),
    ("한겨레",     "hani.co.kr",      ["critical:budget", "critical:safety"]),
    ("뉴스타파",   "newstapa.org",    ["critical:budget"]),
    ("여수신문",   "yeosunews.co.kr", ["verbatim:budget", "partial:safety", "neutral:schedule",
                                        "critical:safety", "verbatim:schedule"]),
    ("노컷뉴스",   "nocutnews.co.kr", ["partial:budget", "neutral:schedule"]),
]

CRITICAL_BODIES = {
    "budget": (
        "2026 여수세계섬박람회 총사업비가 당초 계획보다 800억원 늘어난 것으로 확인됐다. "
        "본지가 입수한 조직위 내부 검토 자료를 분석한 결과, 전시관 조성비가 2년 사이 두 차례 증액됐다. "
        "관람객 350만명이라는 추계의 근거가 된 수요조사는 표본이 400명에 그친 것으로 나타났다. "
        "인근 지자체가 개최한 유사 행사의 실제 관람객은 목표치의 절반에 미치지 못했다. "
        "시의회 예산결산특별위원회 소속 한 의원은 증액 사유에 대한 설명이 없었다고 지적했다. "
        "시는 다음 달 행정사무감사에서 집행 내역을 소명할 예정이다."
    ),
    "safety": (
        "박람회 해상 안전대책의 핵심인 여객선 안전점검이 형식적으로 이뤄지고 있다는 지적이 나온다. "
        "취재 결과 점검 대상 18척 가운데 6척은 선령 20년을 넘긴 노후 선박이었다. "
        "지난해 같은 항로에서 운항 중 기관 고장으로 회항한 사례가 세 차례 있었던 것으로 파악됐다. "
        "안전 요원 배치 계획도 선착장별 인원이 명시되지 않아 실효성 논란이 예상된다. "
        "해양 안전 전문가는 선령 기준을 포함한 구체적 배제 기준이 필요하다고 말했다."
    ),
}

NEUTRAL_BODIES = {
    "schedule": (
        "여수세계섬박람회 기간 박람회장 주변 교통이 통제된다. "
        "통제 구간은 박람회장 진입로 2.4킬로미터이며 시간은 오전 8시부터 오후 10시까지다. "
        "셔틀버스는 여수엑스포역과 종합버스터미널에서 15분 간격으로 다닌다. "
        "임시 주차장은 모두 네 곳이 운영된다. "
        "자세한 노선은 여수시 홈페이지에서 확인할 수 있다."
    ),
}


def make_body(kind: str, pr_body: str) -> str:
    if kind == "verbatim":
        # 조사/어미만 손보고 리드 한 줄 붙인 전형적 전재 기사
        body = pr_body.replace("여수시는", "여수시가").replace("밝혔다", "설명했다")
        return "여수시가 박람회 준비 상황을 발표했다. " + body
    if kind == "partial":
        # 보도자료 절반만 옮기고 자체 문장 두 개를 덧붙인 경우
        sents = [s.strip() for s in pr_body.split(". ") if s.strip()]
        half = ". ".join(sents[: max(2, len(sents) // 2)]) + ". "
        return half + "지역 상공계는 이번 발표를 환영한다는 입장을 냈다. 구체적 집행 일정은 추후 공개될 예정이다."
    return ""


def seed(date: str, reset: bool) -> None:
    conn = connect()
    if reset:
        conn.executescript(
            "DELETE FROM matches; DELETE FROM classifications; DELETE FROM golden_labels; "
            "DELETE FROM articles; DELETE FROM press_releases;"
        )

    now = datetime.now(KST).isoformat()
    day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=KST)
    pr_by_key = {}
    for i, pr in enumerate(PRESS_RELEASES):
        url = f"https://www.yeosu.go.kr/www/govt/news/report/{date}-{pr['key']}"
        pid = hashlib.sha1(url.encode()).hexdigest()[:16]
        pr_by_key[pr["key"]] = pid
        conn.execute(
            """INSERT OR REPLACE INTO press_releases
               (id, source_id, source_name, title, body, url, published_at, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (pid, "yeosu-city", "여수시청 보도자료", pr["title"], pr["body"], url,
             (day - timedelta(days=1)).date().isoformat(), now),
        )

    pr_body_by_key = {p["key"]: p["body"] for p in PRESS_RELEASES}
    pr_title_by_key = {p["key"]: p["title"] for p in PRESS_RELEASES}

    n = 0
    for outlet, domain, specs in OUTLETS:
        for j, spec in enumerate(specs):
            kind, key = spec.split(":")
            if kind in ("verbatim", "partial"):
                body = make_body(kind, pr_body_by_key[key])
                title = pr_title_by_key[key]
            elif kind == "critical":
                body = CRITICAL_BODIES[key]
                title = {"budget": "섬박람회 사업비 800억 증액… 관람객 추계 근거는 표본 400명",
                         "safety": "박람회 여객선 18척 중 6척 선령 20년 초과"}[key]
            else:
                body = NEUTRAL_BODIES[key]
                title = "박람회장 주변 교통통제·셔틀버스 운행"

            url = f"https://{domain}/news/{date.replace('-', '')}/{j}"
            aid = hashlib.sha1(url.split("://", 1)[-1].encode()).hexdigest()[:16]
            conn.execute(
                """INSERT OR REPLACE INTO articles
                   (id, title, description, url, naver_url, outlet, outlet_domain,
                    published_at, target_date, queries, body, body_status, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,'ok',?)""",
                (aid, title, body[:150], url, None, outlet, domain,
                 (day + timedelta(hours=9 + j)).isoformat(), date,
                 json.dumps(["여수세계섬박람회"], ensure_ascii=False), body, now),
            )
            n += 1
    conn.commit()
    conn.close()
    print(f"시드 완료: 보도자료 {len(PRESS_RELEASES)}건, 기사 {n}건 (target_date={date})")
    print("⚠ 전부 합성 데이터입니다. 실제 보도가 아닙니다.")


def mock_classify(date: str) -> None:
    """Claude 없이 파이프라인 뒷단을 돌려보기 위한 규칙 기반 목 분류."""
    conn = connect()
    rows = conn.execute(
        "SELECT id, title, body FROM articles WHERE target_date = ?", (date,)
    ).fetchall()
    CRITIC_CUES = ("확인됐다", "지적", "논란", "부실", "초과", "미치지 못", "감사")
    NEUTRAL_CUES = ("통제", "셔틀버스", "운행", "주차장")
    now = datetime.now(KST).isoformat()
    for r in rows:
        text = r["title"] + " " + r["body"]
        if any(c in text for c in CRITIC_CUES):
            cat, score = "Watchdog", 0.8
        elif any(c in text for c in NEUTRAL_CUES) and "투입" not in text:
            cat, score = "Neutral", 0.0
        else:
            cat, score = "Cheerleader", -0.7
        conn.execute(
            """INSERT OR REPLACE INTO classifications
               (article_id, category, score, confidence, rationale, flagged_issues, model, classified_at)
               VALUES (?,?,?,?,?,?,'mock',?)""",
            (r["id"], cat, score, 0.5, "목(mock) 분류 결과 — 실제 모델 판단 아님", "[]", now),
        )
    conn.commit()
    conn.close()
    print(f"목 분류 {len(rows)}건 (model='mock')")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="데모 데이터 시드")
    ap.add_argument("--date", required=True)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--with-mock-classification", action="store_true")
    a = ap.parse_args()
    seed(a.date, a.reset)
    if a.with_mock_classification:
        mock_classify(a.date)
