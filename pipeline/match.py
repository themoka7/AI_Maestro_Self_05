"""기사 ↔ 보도자료 매칭 및 복제 지표 계산.

후보를 날짜 창(보도자료가 기사보다 앞선다는 가정)으로 먼저 줄인 뒤,
값싼 3-gram Jaccard 로 상위 후보를 추리고, 그 후보에만 비싼 문장 정렬을 돌립니다.
전수 비교하면 기사 500건 x 보도자료 300건 = 15만 쌍이라 감당이 안 됩니다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402
from nlp import align_sentences, document_similarity, jaccard, morphs, ngrams  # noqa: E402

TOP_K = 3           # 기사당 저장할 상위 후보 수
PREFILTER_K = 8     # 정밀 계산에 넘길 후보 수


def parse_day(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None


def main() -> int:
    ap = argparse.ArgumentParser(description="기사와 보도자료 매칭")
    ap.add_argument("--date", required=True)
    ap.add_argument("--config", default="config/event.yaml")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    mcfg = cfg["matching"]
    lookback = timedelta(days=mcfg["lookback_days"])
    lookahead = timedelta(days=mcfg["lookahead_days"])
    sent_threshold = mcfg["sentence_threshold"]

    conn = connect()
    articles = conn.execute(
        """SELECT id, body, published_at FROM articles
           WHERE target_date = ? AND body_status = 'ok'""",
        (args.date,),
    ).fetchall()
    prs = conn.execute(
        "SELECT id, body, title, published_at FROM press_releases WHERE body != ''"
    ).fetchall()

    if not articles:
        print("본문이 확보된 기사가 없습니다. extract_body 를 먼저 돌리세요.")
        return 0
    if not prs:
        print("보도자료가 비어 있습니다. collect_pr 을 먼저 돌리세요.")
        return 0

    # 보도자료 n-gram 은 한 번만 계산해 재사용합니다.
    pr_index = [
        {
            "id": p["id"],
            "body": p["body"],
            "date": parse_day(p["published_at"]),
            "grams": ngrams(morphs(p["body"])),
        }
        for p in prs
    ]

    conn.execute(
        """DELETE FROM matches WHERE article_id IN
           (SELECT id FROM articles WHERE target_date = ?)""",
        (args.date,),
    )

    matched = 0
    for n, art in enumerate(articles, 1):
        a_date = parse_day(art["published_at"])
        a_grams = ngrams(morphs(art["body"]))
        if not a_grams:
            continue

        candidates = []
        for pr in pr_index:
            if a_date and pr["date"]:
                if not (a_date - lookback <= pr["date"] <= a_date + lookahead):
                    continue
            score = jaccard(a_grams, pr["grams"])
            if score > 0.05:
                candidates.append((score, pr))

        candidates.sort(key=lambda t: -t[0])
        results = []
        for _, pr in candidates[:PREFILTER_K]:
            doc = document_similarity(art["body"], pr["body"])
            align = align_sentences(art["body"], pr["body"], threshold=sent_threshold)
            results.append((doc, align, pr))

        # 문서 점수와 복제 문장 비율 중 큰 쪽을 기준으로 정렬합니다.
        # (기사가 보도자료 일부만 그대로 옮긴 경우는 문서 점수가 낮게 나옵니다.)
        results.sort(
            key=lambda t: -max(t[0]["doc_score"], t[0]["containment"], t[1]["copied_sentence_ratio"])
        )
        for rank, (doc, align, pr) in enumerate(results[:TOP_K]):
            conn.execute(
                """INSERT OR REPLACE INTO matches
                   (article_id, pr_id, doc_score, jaccard, lcs,
                    copied_sentence_ratio, sentence_map, is_best)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (art["id"], pr["id"], doc["doc_score"], doc["jaccard"], doc["lcs"],
                 align["copied_sentence_ratio"],
                 json.dumps(align["sentence_map"], ensure_ascii=False),
                 1 if rank == 0 else 0),
            )
        if results:
            matched += 1
        if n % 25 == 0:
            conn.commit()
            print(f"  {n}/{len(articles)} ...", flush=True)
    conn.commit()

    dup_threshold = mcfg["duplication_threshold"]
    stats = conn.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN m.doc_score >= ? OR m.copied_sentence_ratio >= ?
                           THEN 1 ELSE 0 END) duplicated
           FROM articles a LEFT JOIN matches m ON m.article_id = a.id AND m.is_best = 1
           WHERE a.target_date = ? AND a.body_status = 'ok'""",
        (dup_threshold, dup_threshold, args.date),
    ).fetchone()
    dup = stats["duplicated"] or 0
    print(f"\n{args.date}: 기사 {stats['total']}건 중 후보 매칭 {matched}건, "
          f"복제 판정 {dup}건 ({dup / stats['total'] * 100:.1f}%)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
