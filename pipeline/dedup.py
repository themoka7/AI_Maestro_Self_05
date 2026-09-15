"""통신사 전재 클러스터링.

연합뉴스 기사 1건이 30개 매체에 토씨 하나 안 바뀌고 실리는 일이 흔합니다.
이걸 30건으로 세면 "복제율"이 언론사별 행태가 아니라 전재 구조를 반영하게 됩니다.
그래서 같은 날 본문이 거의 동일한 기사끼리 묶고, 가장 먼저 나온 것을 대표(canonical)로 둡니다.
집계는 대표 기사 기준(--canonical-only)과 전체 기준 둘 다 뽑아 비교할 수 있게 합니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402
from nlp import jaccard, morphs, ngrams  # noqa: E402

DUP_THRESHOLD = 0.90


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def main() -> int:
    ap = argparse.ArgumentParser(description="같은 날 전재 기사 클러스터링")
    ap.add_argument("--date", required=True)
    ap.add_argument("--threshold", type=float, default=DUP_THRESHOLD)
    args = ap.parse_args()

    conn = connect()
    rows = conn.execute(
        """SELECT id, body, published_at FROM articles
           WHERE target_date = ? AND body_status = 'ok'
           ORDER BY published_at, id""",
        (args.date,),
    ).fetchall()
    if not rows:
        print("본문이 확보된 기사가 없습니다.")
        return 0

    grams = [ngrams(morphs(r["body"])) for r in rows]
    uf = UnionFind(len(rows))
    for i in range(len(rows)):
        if not grams[i]:
            continue
        for j in range(i + 1, len(rows)):
            if not grams[j]:
                continue
            # 길이 차가 크면 동일 기사일 수 없으므로 비교를 건너뜁니다.
            lo, hi = sorted((len(grams[i]), len(grams[j])))
            if hi and lo / hi < args.threshold:
                continue
            if jaccard(grams[i], grams[j]) >= args.threshold:
                uf.union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(len(rows)):
        clusters.setdefault(uf.find(i), []).append(i)

    multi = 0
    for root, members in clusters.items():
        group_id = rows[root]["id"]
        if len(members) > 1:
            multi += 1
        for idx in members:
            conn.execute(
                "UPDATE articles SET dup_group = ?, is_canonical = ? WHERE id = ?",
                (group_id, 1 if idx == root else 0, rows[idx]["id"]),
            )
    conn.commit()

    canonical = sum(1 for m in clusters.values())
    print(f"{args.date}: 기사 {len(rows)}건 → 고유 {canonical}건 "
          f"(전재 묶음 {multi}개, 중복 제거 {len(rows) - canonical}건)")
    for root, members in sorted(clusters.items(), key=lambda kv: -len(kv[1]))[:5]:
        if len(members) < 2:
            break
        title = conn.execute("SELECT title FROM articles WHERE id = ?",
                             (rows[root]["id"],)).fetchone()["title"]
        print(f"  x{len(members):<3} {title[:50]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
