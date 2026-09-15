"""검증 셋 대비 분류 정확도 측정.

"이 언론사는 홍보성 보도 74%" 를 실명으로 공개하는 서비스입니다.
LLM 분류가 사람 판단과 얼마나 일치하는지 수치로 대지 못하면 그 숫자는 공개하면 안 됩니다.
그래서 이 단계는 선택이 아니라 파이프라인의 필수 관문입니다.

사용 흐름:
  1) python pipeline/evaluate.py sample --date 2026-09-14 --n 100 > label.csv
  2) label.csv 의 gold 열을 사람이 직접 채웁니다 (Watchdog/Cheerleader/Neutral)
  3) python pipeline/evaluate.py load label.csv
  4) python pipeline/evaluate.py report --date 2026-09-14
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

KST = timezone(timedelta(hours=9), "KST")
CATEGORIES = ["Watchdog", "Cheerleader", "Neutral"]


def cmd_sample(args) -> int:
    conn = connect()
    rows = conn.execute(
        """SELECT a.id, a.outlet, a.title, SUBSTR(a.body, 1, 300) AS excerpt, a.url
           FROM articles a LEFT JOIN golden_labels g ON g.article_id = a.id
           WHERE a.target_date = ? AND a.body_status = 'ok' AND g.article_id IS NULL""",
        (args.date,),
    ).fetchall()
    random.seed(args.seed)
    picked = random.sample(rows, min(args.n, len(rows)))

    writer = csv.writer(sys.stdout)
    writer.writerow(["article_id", "gold", "outlet", "title", "excerpt", "url"])
    for r in picked:
        writer.writerow([r["id"], "", r["outlet"], r["title"], r["excerpt"], r["url"]])
    print(f"\n# {len(picked)}건 추출. gold 열을 {'/'.join(CATEGORIES)} 로 채운 뒤 "
          f"`evaluate.py load` 하세요.", file=sys.stderr)
    conn.close()
    return 0


def cmd_load(args) -> int:
    conn = connect()
    now = datetime.now(KST).isoformat()
    loaded = skipped = 0
    with Path(args.path).open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            gold = (row.get("gold") or "").strip()
            if gold not in CATEGORIES:
                skipped += 1
                continue
            conn.execute(
                """INSERT OR REPLACE INTO golden_labels
                   (article_id, category, labeler, note, labeled_at) VALUES (?,?,?,?,?)""",
                (row["article_id"], gold, args.labeler, row.get("note", ""), now),
            )
            loaded += 1
    conn.commit()
    print(f"라벨 {loaded}건 적재 (미기입/무효 {skipped}건 건너뜀)")
    conn.close()
    return 0


def cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    """두 평가자(사람 vs 모델)의 우연 일치를 제외한 일치도."""
    n = len(pairs)
    if n == 0:
        return 0.0
    observed = sum(1 for a, b in pairs if a == b) / n
    expected = 0.0
    for c in CATEGORIES:
        pa = sum(1 for a, _ in pairs if a == c) / n
        pb = sum(1 for _, b in pairs if b == c) / n
        expected += pa * pb
    if expected >= 1.0:
        return 1.0
    return (observed - expected) / (1 - expected)


def cmd_report(args) -> int:
    conn = connect()
    where = "AND a.target_date = ?" if args.date else ""
    params = (args.date,) if args.date else ()
    rows = conn.execute(
        f"""SELECT g.category AS gold, c.category AS pred, c.confidence, a.outlet, a.title, a.id
            FROM golden_labels g
            JOIN articles a ON a.id = g.article_id
            JOIN classifications c ON c.article_id = g.article_id
            WHERE 1=1 {where}""",
        params,
    ).fetchall()
    if not rows:
        print("검증 셋과 분류 결과가 겹치는 기사가 없습니다. "
              "라벨링 후 classify 를 돌렸는지 확인하세요.")
        return 1

    pairs = [(r["gold"], r["pred"]) for r in rows]
    n = len(pairs)
    acc = sum(1 for a, b in pairs if a == b) / n
    kappa = cohens_kappa(pairs)

    print(f"검증 셋 {n}건 | 정확도 {acc * 100:.1f}% | Cohen's κ {kappa:.3f}")
    verdict = ("κ 0.6 미만 — 일치도가 낮습니다. 프롬프트/분류 기준을 고치기 전에는 "
               "언론사별 수치를 외부 공개하지 마세요."
               if kappa < 0.6 else
               "κ 0.6 이상 — 공개 가능한 수준의 일치도입니다. 그래도 방법론과 함께 표기하세요.")
    print(f"  → {verdict}\n")

    print("혼동 행렬 (행=사람, 열=모델)")
    header = " " * 14 + "".join(f"{c:>14}" for c in CATEGORIES)
    print(header)
    for g in CATEGORIES:
        cells = [sum(1 for a, b in pairs if a == g and b == p) for p in CATEGORIES]
        print(f"{g:<14}" + "".join(f"{v:>14}" for v in cells))

    print("\n클래스별 정밀도/재현율")
    for c in CATEGORIES:
        tp = sum(1 for a, b in pairs if a == c and b == c)
        fp = sum(1 for a, b in pairs if a != c and b == c)
        fn = sum(1 for a, b in pairs if a == c and b != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        print(f"  {c:<12} P={prec:.2f}  R={rec:.2f}  F1={f1:.2f}  (n={sum(1 for a, _ in pairs if a == c)})")

    mismatches = [r for r in rows if r["gold"] != r["pred"]]
    if mismatches:
        print(f"\n불일치 {len(mismatches)}건 (상위 10):")
        for r in mismatches[:10]:
            print(f"  [{r['gold']} → {r['pred']}] conf={r['confidence']:.2f} "
                  f"{r['outlet']} | {r['title'][:44]}")
    conn.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="분류 검증 셋 관리 및 평가")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="라벨링용 표본 CSV 출력")
    s.add_argument("--date", required=True)
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=42)
    s.set_defaults(func=cmd_sample)

    l = sub.add_parser("load", help="라벨 CSV 적재")
    l.add_argument("path")
    l.add_argument("--labeler", default="")
    l.set_defaults(func=cmd_load)

    r = sub.add_parser("report", help="정확도/κ 리포트")
    r.add_argument("--date", default=None)
    r.set_defaults(func=cmd_report)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
