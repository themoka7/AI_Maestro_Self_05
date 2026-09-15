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
                   SUM(CASE WHEN c.category = 'Watchdog'    THEN 1 ELSE 0 END) AS watchdog,
                   SUM(CASE WHEN c.category = 'Cheerleader' THEN 1 ELSE 0 END) AS cheerleader,
                   SUM(CASE WHEN c.category = 'Neutral'     THEN 1 ELSE 0 END) AS neutral,
                   SUM(CASE WHEN COALESCE(m.doc_score, 0) >= ?
                             OR COALESCE(m.copied_sentence_ratio, 0) >= ?
                            THEN 1 ELSE 0 END) AS duplicated
            FROM articles a
            JOIN classifications c ON c.article_id = a.id
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

    g_w = sum(r["watchdog"] for r in rows) / total
    g_n = sum(r["neutral"] for r in rows) / total
    g_c = sum(r["cheerleader"] for r in rows) / total
    g_d = sum(r["duplicated"] for r in rows) / total

    outlets = []
    for r in rows:
        n = r["n"]
        w = shrink(r["watchdog"], n, g_w, prior)
        neu = shrink(r["neutral"], n, g_n, prior)
        dup = shrink(r["duplicated"], n, g_d, prior)
        raw = 0.6 * w + 0.4 * neu - 0.5 * dup
        outlets.append({
            "outlet": r["outlet"],
            "articles": n,
            "watchdog": r["watchdog"],
            "cheerleader": r["cheerleader"],
            "neutral": r["neutral"],
            "duplicated": r["duplicated"],
            # 관측 비율 (표시용)
            "watchdog_rate": round(r["watchdog"] / n * 100, 1),
            "cheerleader_rate": round(r["cheerleader"] / n * 100, 1),
            "neutral_rate": round(r["neutral"] / n * 100, 1),
            "duplication_rate": round(r["duplicated"] / n * 100, 1),
            # 보정 후 점수 (랭킹용)
            "autonomy_score": normalize(raw),
            "sufficient_sample": n >= min_articles,
        })

    outlets.sort(key=lambda o: (o["sufficient_sample"], o["autonomy_score"]), reverse=True)
    for i, o in enumerate(outlets, 1):
        o["rank"] = i if o["sufficient_sample"] else None

    return {
        "date": date,
        "basis": "canonical" if canonical_only else "all",
        "totals": {
            "articles": total,
            "watchdog_rate": round(g_w * 100, 1),
            "cheerleader_rate": round(g_c * 100, 1),
            "neutral_rate": round(g_n * 100, 1),
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
    print(f"{args.date} ({result['basis']}) 전체 {t['articles']}건 | "
          f"복제 {t['duplication_rate']}% | 감시 {t['watchdog_rate']}% | "
          f"홍보 {t['cheerleader_rate']}% | 중립 {t['neutral_rate']}%\n")
    print(f"{'순위':<5}{'언론사':<18}{'기사':>5}{'자율성':>8}{'복제%':>8}{'감시%':>8}{'홍보%':>8}")
    for o in result["outlets"]:
        rank = str(o["rank"]) if o["rank"] else "-"
        mark = "" if o["sufficient_sample"] else "  (표본부족)"
        print(f"{rank:<5}{o['outlet']:<18}{o['articles']:>5}{o['autonomy_score']:>8.1f}"
              f"{o['duplication_rate']:>8.1f}{o['watchdog_rate']:>8.1f}"
              f"{o['cheerleader_rate']:>8.1f}{mark}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
