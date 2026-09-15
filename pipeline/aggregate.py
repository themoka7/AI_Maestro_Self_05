"""날짜를 가로지르는 언론사별 집계 — 이 프로젝트의 최종 산출물.

하루치만으로는 언론사를 판단할 수 없습니다. 기사 2~3건으로는 표본이 너무 작고,
그날 무슨 보도자료가 나왔느냐에 따라 비율이 크게 흔들립니다. 날짜를 누적해야
비로소 "이 매체는 계속 이런 식으로 쓴다"는 말을 할 수 있습니다.

집계에서 반드시 지킬 것: **일별 비율을 평균내지 않습니다.**
기사 40건인 날의 복제율 50%와 기사 2건인 날의 복제율 100%를 단순 평균하면 75%가
나오지만 실제는 (20+2)/42 = 52.4% 입니다. 원시 건수를 합산한 뒤 비율을 계산합니다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from history import DAILY_DIR, HISTORY  # noqa: E402
from score import normalize, shrink  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")
OUT_FILE = HISTORY / "outlets.json"

COUNT_FIELDS = ("articles", "classified", "watchdog", "cheerleader", "neutral", "duplicated")


def load_daily(days: int | None) -> list[dict]:
    if not DAILY_DIR.exists():
        return []
    paths = sorted(DAILY_DIR.glob("*.json"))
    if days:
        paths = paths[-days:]
    out = []
    for p in paths:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            print(f"  건너뜀 {p.name}: {e}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="언론사별 누적 집계")
    ap.add_argument("--config", default="config/event.yaml")
    ap.add_argument("--days", type=int, default=0, help="최근 N일만 집계 (0=전체)")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    prior = float(cfg["scoring"]["prior_weight"])
    min_articles = int(cfg["scoring"]["min_articles"])

    dailies = load_daily(args.days or None)
    if not dailies:
        print("집계할 일별 데이터가 없습니다. export 를 먼저 돌리세요.")
        return 1

    # 언론사별 원시 건수 합산 + 일별 시계열
    acc: dict[str, dict] = {}
    for day in dailies:
        date = day["date"]
        for o in day["outlets"]:
            name = o["outlet"]
            entry = acc.setdefault(name, {
                "outlet": name,
                **{f: 0 for f in COUNT_FIELDS},
                "days": 0,
                "series": [],
            })
            for f in COUNT_FIELDS:
                entry[f] += o.get(f, 0) or 0
            entry["days"] += 1
            entry["series"].append({
                "date": date,
                "articles": o["articles"],
                "duplication_rate": o["duplication_rate"],
                "watchdog_rate": o["watchdog_rate"],
                "autonomy_score": o["autonomy_score"],
            })

    total = sum(e["articles"] for e in acc.values())
    if not total:
        print("집계할 기사가 없습니다.")
        return 1

    # 분류 비율의 분모는 분류된 기사 수입니다 (전체 기사가 아니라).
    classified_total = sum(e["classified"] for e in acc.values())
    has_classification = classified_total > 0
    denom = classified_total or 1
    g_w = sum(e["watchdog"] for e in acc.values()) / denom
    g_n = sum(e["neutral"] for e in acc.values()) / denom
    g_c = sum(e["cheerleader"] for e in acc.values()) / denom
    g_d = sum(e["duplicated"] for e in acc.values()) / total

    outlets = []
    for e in acc.values():
        n = e["articles"]
        k = e["classified"]
        dup = shrink(e["duplicated"], n, g_d, prior)
        if k:
            w = shrink(e["watchdog"], k, g_w, prior)
            neu = shrink(e["neutral"], k, g_n, prior)
            autonomy = normalize(0.6 * w + 0.4 * neu - 0.5 * dup)
        else:
            autonomy = None

        series = sorted(e["series"], key=lambda s: s["date"])
        # 최근 7일 대 그 이전의 자율성 점수 변화 (추세)
        recent = [s["autonomy_score"] for s in series[-7:] if s["autonomy_score"] is not None]
        prior_window = [s["autonomy_score"] for s in series[:-7] if s["autonomy_score"] is not None]
        trend = (round(sum(recent) / len(recent) - sum(prior_window) / len(prior_window), 1)
                 if recent and prior_window else None)

        outlets.append({
            "outlet": e["outlet"],
            "articles": n,
            "classified": k,
            "activeDays": e["days"],
            "watchdog": e["watchdog"],
            "cheerleader": e["cheerleader"],
            "neutral": e["neutral"],
            "duplicated": e["duplicated"],
            "watchdog_rate": round(e["watchdog"] / k * 100, 1) if k else None,
            "cheerleader_rate": round(e["cheerleader"] / k * 100, 1) if k else None,
            "neutral_rate": round(e["neutral"] / k * 100, 1) if k else None,
            "duplication_rate": round(e["duplicated"] / n * 100, 1),
            "autonomy_score": autonomy,
            "sufficient_sample": n >= min_articles,
            "trend": trend,
            "series": series,
        })

    if has_classification:
        outlets.sort(key=lambda o: (o["sufficient_sample"], o["autonomy_score"] or 0), reverse=True)
    else:
        outlets.sort(key=lambda o: (not o["sufficient_sample"], o["duplication_rate"]))
    for i, o in enumerate(outlets, 1):
        o["rank"] = i if o["sufficient_sample"] else None

    dates = [d["date"] for d in dailies]
    payload = {
        "event": dailies[-1]["event"],
        "window": {"from": dates[0], "to": dates[-1], "days": len(dates)},
        "generatedAt": datetime.now(KST).isoformat(),
        "params": dailies[-1]["params"],
        # 한 날이라도 실측이 섞여 있으면 데모가 아닙니다. 보수적으로 판단합니다.
        "demo": all(d.get("demo") for d in dailies),
        "hasClassification": has_classification,
        "classifiedArticles": classified_total,
        "totals": {
            "articles": total,
            "watchdog_rate": round(g_w * 100, 1) if has_classification else None,
            "cheerleader_rate": round(g_c * 100, 1) if has_classification else None,
            "neutral_rate": round(g_n * 100, 1) if has_classification else None,
            "duplication_rate": round(g_d * 100, 1),
        },
        "daily": [
            {"date": d["date"], **d["totals"]} for d in dailies
        ],
        "outlets": outlets,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    t = payload["totals"]
    print(f"누적 집계 {dates[0]} ~ {dates[-1]} ({len(dates)}일, 기사 {total}건)")
    if has_classification:
        print(f"  전체: 복제 {t['duplication_rate']}% | 감시 {t['watchdog_rate']}% | "
              f"홍보 {t['cheerleader_rate']}%\n")
    else:
        print(f"  전체: 복제 {t['duplication_rate']}%")
        print("  분류 결과가 없어 자율성 점수는 비어 있습니다 (ANTHROPIC_API_KEY 필요).\n")

    def fmt(v):
        return f"{v:>8.1f}" if isinstance(v, (int, float)) else f"{'-':>8}"

    print(f"{'순위':<5}{'언론사':<18}{'기사':>5}{'일수':>5}{'자율성':>8}{'복제%':>8}{'감시%':>8}{'추세':>7}")
    for o in outlets:
        rank = str(o["rank"]) if o["rank"] else "-"
        trend = f"{o['trend']:+.1f}" if o["trend"] is not None else "–"
        mark = "" if o["sufficient_sample"] else "  (표본부족)"
        print(f"{rank:<5}{o['outlet']:<18}{o['articles']:>5}{o['activeDays']:>5}"
              f"{fmt(o['autonomy_score'])}{fmt(o['duplication_rate'])}"
              f"{fmt(o['watchdog_rate'])}{trend:>7}{mark}")
    print(f"\n→ {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
