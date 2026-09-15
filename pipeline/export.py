"""대시보드용 JSON 산출.

Next.js 가 SQLite 를 직접 읽게 하면 네이티브 모듈(better-sqlite3) 빌드가 걸립니다.
파이프라인이 JSON 을 떨궈 두고 웹은 그걸 읽는 구조가 훨씬 단순하고, 나중에 DB 로
갈아타더라도 이 JSON 계약만 유지하면 프런트는 건드릴 필요가 없습니다.

산출물은 data/history/ 에 날짜별로 쌓입니다. GitHub Actions 러너는 매번 초기화되므로
이 JSON 이 리포지토리에 커밋되는 단일 저장소이고, SQLite 는 매 실행마다 재구성됩니다.

저작권 주의: 기본값은 --excerpt-only 로, 보도자료와 매칭된 문장만 내보냅니다.
기사 전문을 그대로 실어 공개하면 복제를 지적하는 서비스가 복제를 하는 꼴이 됩니다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402
from score import compute  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "history"
# 대조 화면을 만들 가치가 있는 최소 유사도. 이 아래는 보여줄 게 없습니다.
DETAIL_MIN_SIMILARITY = 0.20


def build_articles(conn, date: str, dup_threshold: float) -> list[dict]:
    rows = conn.execute(
        """SELECT a.id, a.title, a.url, a.outlet, a.published_at, a.is_canonical, a.dup_group,
                  c.category, c.score, c.confidence, c.rationale, c.flagged_issues,
                  m.doc_score, m.copied_sentence_ratio, m.pr_id,
                  p.title AS pr_title, p.url AS pr_url, p.source_name AS pr_source,
                  p.published_at AS pr_published_at
           FROM articles a
           LEFT JOIN classifications c ON c.article_id = a.id
           LEFT JOIN matches m ON m.article_id = a.id AND m.is_best = 1
           LEFT JOIN press_releases p ON p.id = m.pr_id
           WHERE a.target_date = ? AND a.body_status = 'ok'
           ORDER BY a.published_at""",
        (date,),
    ).fetchall()

    out = []
    for r in rows:
        dup = max(r["doc_score"] or 0.0, r["copied_sentence_ratio"] or 0.0)
        # 같은 dup_group 안에 몇 개 매체가 실었는지 = 전재 확산 규모
        spread = conn.execute(
            "SELECT COUNT(*) c FROM articles WHERE dup_group = ? AND dup_group IS NOT NULL",
            (r["dup_group"],),
        ).fetchone()["c"] if r["dup_group"] else 1

        out.append({
            "id": r["id"],
            "title": r["title"],
            "url": r["url"],
            "outlet": r["outlet"],
            "publishedAt": r["published_at"],
            "category": r["category"],
            "score": r["score"],
            "confidence": r["confidence"],
            "rationale": r["rationale"] or "",
            "flaggedIssues": json.loads(r["flagged_issues"] or "[]"),
            "duplication": round(dup * 100, 1),
            "isDuplicated": dup >= dup_threshold,
            "docScore": round((r["doc_score"] or 0.0) * 100, 1),
            "copiedSentenceRatio": round((r["copied_sentence_ratio"] or 0.0) * 100, 1),
            "isCanonical": bool(r["is_canonical"]),
            "syndicationSpread": spread,
            "pressRelease": None if not r["pr_id"] else {
                "id": r["pr_id"],
                "title": r["pr_title"],
                "url": r["pr_url"],
                "source": r["pr_source"],
                "publishedAt": r["pr_published_at"],
            },
        })
    return out


def build_detail(conn, article_id: str, excerpt_only: bool) -> dict | None:
    """문장 대조 데이터. 저장 용량이 기사 수 x 문장 수로 불어나므로 두 가지를 줄입니다.

      1. 보도자료와 매칭되지 않은 문장은 아예 넣지 않습니다.
         excerpt 모드에서 어차피 가려질 것이라 자리만 차지했고, 실제 기사에서는
         이런 문장이 전체의 절반을 넘습니다. 몇 개를 생략했는지만 남깁니다.
      2. 유사도가 바닥인 기사는 파일을 만들지 않습니다.
         대조 화면에 보여줄 것이 없는데 리포지토리에 매일 쌓일 이유가 없습니다.
    """
    row = conn.execute(
        """SELECT m.sentence_map, m.doc_score, m.copied_sentence_ratio,
                  p.title AS pr_title, p.url AS pr_url, p.source_name
           FROM matches m JOIN press_releases p ON p.id = m.pr_id
           WHERE m.article_id = ? AND m.is_best = 1""",
        (article_id,),
    ).fetchone()
    if not row:
        return None
    if max(row["doc_score"], row["copied_sentence_ratio"]) < DETAIL_MIN_SIMILARITY:
        return None

    smap = json.loads(row["sentence_map"])
    if excerpt_only:
        kept = [s for s in smap if s["sim"] > 0]
        omitted = len(smap) - len(kept)
        smap = kept
    else:
        omitted = 0

    return {
        "articleId": article_id,
        "pressRelease": {
            "title": row["pr_title"], "url": row["pr_url"], "source": row["source_name"],
        },
        "docScore": round(row["doc_score"] * 100, 1),
        "copiedSentenceRatio": round(row["copied_sentence_ratio"] * 100, 1),
        "sentences": smap,
        "omittedSentences": omitted,
        "excerptOnly": excerpt_only,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="대시보드용 JSON 내보내기")
    ap.add_argument("--date", required=True)
    ap.add_argument("--config", default="config/event.yaml")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--full-text", action="store_true",
                    help="비매칭 문장까지 내보냄 (내부 검토용. 공개 배포에는 쓰지 마세요)")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    dup_threshold = cfg["matching"]["duplication_threshold"]
    conn = connect()

    # 언론사 점수는 전재본 포함 전체 기준 (전재 자체가 측정 대상 행태)
    scores = compute(conn, args.date, cfg, canonical_only=False)
    if not scores["totals"]:
        print("내보낼 데이터가 없습니다.")
        return 1
    # 고유 기사 기준은 "이날 실제로 몇 개의 서로 다른 기사가 있었나" 참고용
    scores_unique = compute(conn, args.date, cfg, canonical_only=True)
    articles = build_articles(conn, args.date, dup_threshold)

    coverage = conn.execute(
        """SELECT body_status, COUNT(*) c FROM articles
           WHERE target_date = ? GROUP BY body_status""",
        (args.date,),
    ).fetchall()
    # 분류가 전부 목(mock)이면 합성 데이터입니다. 공개 화면에서 실측과 구분해야 하므로
    # 사람이 지우는 것에 기대지 않고 산출물 자체에 표시합니다.
    models = {r["model"] for r in conn.execute(
        """SELECT DISTINCT c.model FROM classifications c
           JOIN articles a ON a.id = c.article_id WHERE a.target_date = ?""",
        (args.date,),
    )}
    is_demo = bool(models) and models == {"mock"}

    golden = conn.execute(
        """SELECT COUNT(*) c FROM golden_labels g JOIN articles a ON a.id = g.article_id
           WHERE a.target_date = ?""",
        (args.date,),
    ).fetchone()["c"]

    payload = {
        "event": cfg["event"],
        "date": args.date,
        "generatedAt": __import__("datetime").datetime.now().astimezone().isoformat(),
        "totals": scores["totals"],
        "totalsUniqueOnly": scores_unique["totals"],
        "params": scores["params"],
        "outlets": scores["outlets"],
        "articles": articles,
        "coverage": {r["body_status"]: r["c"] for r in coverage},
        "goldenLabeled": golden,
        "excerptOnly": not args.full_text,
        "demo": is_demo,
    }

    out = Path(args.out)
    daily_dir = out / "daily"
    details_dir = out / "details" / args.date
    daily_dir.mkdir(parents=True, exist_ok=True)
    if details_dir.exists():
        shutil.rmtree(details_dir)
    details_dir.mkdir(parents=True, exist_ok=True)

    (daily_dir / f"{args.date}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    n_detail = 0
    for a in articles:
        detail = build_detail(conn, a["id"], excerpt_only=not args.full_text)
        if detail:
            (details_dir / f"{a['id']}.json").write_text(
                json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
            n_detail += 1

    from history import rebuild_index
    dates = rebuild_index()

    print(f"내보내기 완료 → {out}")
    print(f"  daily/{args.date}.json  (기사 {len(articles)}건, "
          f"언론사 {len(scores['outlets'])}곳)")
    print(f"  보유 날짜 {len(dates)}일")
    print(f"  details/{args.date}/*.json  {n_detail}건"
          + ("  [매칭 문장만]" if not args.full_text else "  [전문 포함 — 공개 배포 금지]"))
    if is_demo:
        print("  ℹ 합성 데모 데이터 (model=mock) — 산출물에 demo=true 로 표시됨")
    elif golden == 0:
        print("  ⚠ 검증 라벨 0건 — evaluate.py 로 검증 전에는 대외 공개 금지")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
