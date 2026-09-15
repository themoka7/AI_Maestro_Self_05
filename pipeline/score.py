"""언론사 자율성 점수 산출.

PRD 4.3 의 공식은 그대로 쓰되 두 가지를 고칩니다.

1) 정규화가 정의돼 있지 않았습니다.
   raw = 0.6*W + 0.4*N - 0.5*PR  의 값역은 [-0.5, 0.6] 입니다.
   (W=N=0, PR=1 일 때 최소, W=1 일 때 최대)
   → normalized = (raw + 0.5) / 1.1 * 100  으로 0~100 에 정확히 매핑합니다.

2) 집계 기준: 언론사 점수는 "그 언론사가 실제로 내보낸 모든 기사" 기준입니다.
   통신사 기사를 그대로 받아 싣는 것 자체가 이 지표가 측정하려는 행태이므로,
   전재본을 빼고 세면 정작 의존도가 높은 매체가 집계에서 사라집니다.
   전재 클러스터(dup_group)는 "이날 고유 기사가 몇 건이었나" 하는 이벤트 레벨 통계에만 씁니다.

3) 표본이 적은 매체가 랭킹 1위를 먹는 문제.
   기사 2건 중 1건이 Watchdog 이면 비율 50% 로 전국지를 앞지릅니다.
   → 각 비율을 전체 평균 쪽으로 당기는 베이지안 shrinkage 를 적용하고,
     최소 기사 수 미만은 랭킹에서 'insufficient' 로 따로 표시합니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

RAW_MIN, RAW_MAX = -0.5, 0.6


def normalize(raw: float) -> float:
    return round((raw - RAW_MIN) / (RAW_MAX - RAW_MIN) * 100, 1)


def shrink(count: int, n: int, global_rate: float, prior: float) -> float:
    """표본이 작을수록 전체 평균 쪽으로 당깁니다."""
    if n + prior == 0:
        return global_rate
    return (count + prior * global_rate) / (n + prior)


def fetch_rows(conn, date: str, canonical_only: bool, dup_threshold: float):
    where_canonical = "AND a.is_canonical = 1" if canonical_only else ""
    return conn.execute(
        f"""SELECT a.outlet,
                   COUNT(*) AS n,
                   SUM(CASE WHEN c.article_id IS NOT NULL THEN 1 ELSE 0 END) AS classified,
                   SUM(CASE WHEN c.category = 'Watchdog'    THEN 1 ELSE 0 END) AS watchdog,
                   SUM(CASE WHEN c.category = 'Cheerleader' THEN 1 ELSE 0 END) AS cheerleader,
                   SUM(CASE WHEN c.category = 'Neutral'     THEN 1 ELSE 0 END) AS neutral,
                   SUM(CASE WHEN COALESCE(m.doc_score, 0) >= ?
                             OR COALESCE(m.copied_sentence_ratio, 0) >= ?
                            THEN 1 ELSE 0 END) AS duplicated
            FROM articles a
            LEFT JOIN classifications c ON c.article_id = a.id
            LEFT JOIN matches m ON m.article_id = a.id AND m.is_best = 1
            WHERE a.target_date = ? AND a.body_status = 'ok' {where_canonical}
            GROUP BY a.outlet""",
        (dup_threshold, dup_threshold, date),
    ).fetchall()


def compute(conn, date: str, cfg: dict, canonical_only: bool = False) -> dict:
    dup_threshold = cfg["matching"]["duplication_threshold"]
    prior = float(cfg["scoring"]["prior_weight"])
    min_articles = int(cfg["scoring"]["min_articles"])

    rows = fetch_rows(conn, date, canonical_only, dup_threshold)
    total = sum(r["n"] for r in rows)
    if not total:
        return {"date": date, "totals": None, "outlets": []}

    # 분류(Anthropic 키)가 없어도 복제율은 순수 텍스트 비교라 계산됩니다.
    # 그 경우 자율성 점수만 포기하고 나머지는 그대로 내보냅니다 — 수집한 기사와
    # 이미 쓴 API 호출을 키 하나 때문에 버리지 않기 위함입니다.
    classified_total = sum(r["classified"] for r in rows)
    has_classification = classified_total > 0

    denom = classified_total or 1
    g_w = sum(r["watchdog"] for r in rows) / denom
    g_n = sum(r["neutral"] for r in rows) / denom
    g_c = sum(r["cheerleader"] for r in rows) / denom
    g_d = sum(r["duplicated"] for r in rows) / total

    outlets = []
    for r in rows:
        n = r["n"]
        k = r["classified"]
        dup = shrink(r["duplicated"], n, g_d, prior)
        if k:
            w = shrink(r["watchdog"], k, g_w, prior)
            neu = shrink(r["neutral"], k, g_n, prior)
            autonomy = normalize(0.6 * w + 0.4 * neu - 0.5 * dup)
        else:
            # 분류가 없으면 감시·중립 비율을 0 으로 두고 점수를 매기면 안 됩니다.
            # "취재를 안 했다"가 아니라 "재지 못했다"이므로 값을 비웁니다.
            autonomy = None
        outlets.append({
            "outlet": r["outlet"],
            "articles": n,
            "classified": k,
            "watchdog": r["watchdog"],
            "cheerleader": r["cheerleader"],
            "neutral": r["neutral"],
            "duplicated": r["duplicated"],
            # 관측 비율 (표시용)
            # 분류 비율의 분모는 '분류된 기사'입니다. 전체 기사로 나누면 분류가
            # 일부만 된 날에 모든 비율이 실제보다 낮게 보입니다.
            "watchdog_rate": round(r["watchdog"] / k * 100, 1) if k else None,
            "cheerleader_rate": round(r["cheerleader"] / k * 100, 1) if k else None,
            "neutral_rate": round(r["neutral"] / k * 100, 1) if k else None,
            "duplication_rate": round(r["duplicated"] / n * 100, 1),
            # 보정 후 점수 (랭킹용). 분류가 없으면 None.
            "autonomy_score": autonomy,
            "sufficient_sample": n >= min_articles,
        })

    # 자율성 점수가 없으면 복제율이 낮은 순으로 세웁니다 (그때 유일하게 있는 지표).
    if has_classification:
        outlets.sort(key=lambda o: (o["sufficient_sample"], o["autonomy_score"] or 0), reverse=True)
    else:
        outlets.sort(key=lambda o: (not o["sufficient_sample"], o["duplication_rate"]))
    for i, o in enumerate(outlets, 1):
        o["rank"] = i if o["sufficient_sample"] else None

    return {
        "date": date,
        "basis": "canonical" if canonical_only else "all",
        "hasClassification": has_classification,
        "classifiedArticles": classified_total,
        "totals": {
            "articles": total,
            "watchdog_rate": round(g_w * 100, 1) if has_classification else None,
            "cheerleader_rate": round(g_c * 100, 1) if has_classification else None,
            "neutral_rate": round(g_n * 100, 1) if has_classification else None,
            "duplication_rate": round(g_d * 100, 1),
        },
        "params": {
            "duplication_threshold": dup_threshold,
            "prior_weight": prior,
            "min_articles": min_articles,
        },
        "outlets": outlets,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="언론사 자율성 점수 계산")
    ap.add_argument("--date", required=True)
    ap.add_argument("--config", default="config/event.yaml")
    ap.add_argument("--canonical-only", action="store_true",
                    help="전재본을 제외하고 대표 기사만 집계 (이벤트 레벨 고유 기사 통계용). "
                         "기본값은 언론사가 실제로 내보낸 전체 기사 기준입니다.")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    conn = connect()
    result = compute(conn, args.date, cfg, canonical_only=args.canonical_only)
    if not result["totals"]:
        print("집계할 데이터가 없습니다.")
        return 0

    t = result["totals"]
    if result["hasClassification"]:
        print(f"{args.date} ({result['basis']}) 전체 {t['articles']}건 | "
              f"복제 {t['duplication_rate']}% | 감시 {t['watchdog_rate']}% | "
              f"홍보 {t['cheerleader_rate']}% | 중립 {t['neutral_rate']}%\n")
    else:
        print(f"{args.date} ({result['basis']}) 전체 {t['articles']}건 | "
              f"복제 {t['duplication_rate']}%")
        print("분류 결과가 없어 자율성 점수는 산출하지 않았습니다 "
              "(ANTHROPIC_API_KEY 필요).\n")

    def fmt(v):
        return f"{v:>8.1f}" if isinstance(v, (int, float)) else f"{'-':>8}"

    print(f"{'순위':<5}{'언론사':<18}{'기사':>5}{'자율성':>8}{'복제%':>8}{'감시%':>8}{'홍보%':>8}")
    for o in result["outlets"]:
        rank = str(o["rank"]) if o["rank"] else "-"
        mark = "" if o["sufficient_sample"] else "  (표본부족)"
        print(f"{rank:<5}{o['outlet']:<18}{o['articles']:>5}"
              f"{fmt(o['autonomy_score'])}{fmt(o['duplication_rate'])}"
              f"{fmt(o['watchdog_rate'])}{fmt(o['cheerleader_rate'])}{mark}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
