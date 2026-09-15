"""SQLite 스키마 및 커넥션. 하루 수백~수천 건 규모에서는 이걸로 충분합니다."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "parallax.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- 지자체/조직위 공식 보도자료
CREATE TABLE IF NOT EXISTS press_releases (
    id           TEXT PRIMARY KEY,   -- sha1(url)
    source_id    TEXT NOT NULL,
    source_name  TEXT NOT NULL,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL UNIQUE,
    published_at TEXT,               -- ISO8601 (KST)
    fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pr_published ON press_releases(published_at);

-- 네이버 뉴스 검색 API로 수집한 기사
CREATE TABLE IF NOT EXISTS articles (
    id             TEXT PRIMARY KEY, -- sha1(정규화 URL)
    title          TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    url            TEXT NOT NULL UNIQUE,   -- originallink 정규화
    naver_url      TEXT,
    outlet         TEXT NOT NULL,          -- 도메인에서 역산
    outlet_domain  TEXT NOT NULL,
    published_at   TEXT NOT NULL,          -- ISO8601 (KST)
    target_date    TEXT NOT NULL,          -- 이 기사가 속한 수집 대상 일자 (YYYY-MM-DD)
    queries        TEXT NOT NULL DEFAULT '[]',  -- 이 기사를 잡아낸 검색어들 (JSON)
    body           TEXT NOT NULL DEFAULT '',
    body_status    TEXT NOT NULL DEFAULT 'pending', -- pending|ok|empty|blocked|failed
    body_error     TEXT,
    fetched_at     TEXT NOT NULL,
    -- 통신사 전재 클러스터. 같은 본문이 여러 매체에 그대로 실린 경우를 묶습니다.
    dup_group      TEXT,
    is_canonical   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_art_target ON articles(target_date);
CREATE INDEX IF NOT EXISTS idx_art_outlet ON articles(outlet);
CREATE INDEX IF NOT EXISTS idx_art_status ON articles(body_status);

-- 기사 ↔ 보도자료 유사도. 기사당 후보 전부가 아니라 상위 N건만 저장합니다.
CREATE TABLE IF NOT EXISTS matches (
    article_id            TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    pr_id                 TEXT NOT NULL REFERENCES press_releases(id) ON DELETE CASCADE,
    doc_score             REAL NOT NULL,  -- 0.6*jaccard + 0.4*lcs  (0~1)
    jaccard               REAL NOT NULL,
    lcs                   REAL NOT NULL,
    copied_sentence_ratio REAL NOT NULL,  -- 보도자료에서 그대로 옮긴 문장 비율 (0~1)
    sentence_map          TEXT NOT NULL DEFAULT '[]',  -- 문장별 매칭 결과 (JSON) → diff 하이라이트용
    is_best               INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (article_id, pr_id)
);
CREATE INDEX IF NOT EXISTS idx_match_best ON matches(article_id, is_best);

-- Claude 분류 결과
CREATE TABLE IF NOT EXISTS classifications (
    article_id    TEXT PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    category      TEXT NOT NULL,   -- Watchdog|Cheerleader|Neutral
    score         REAL NOT NULL,   -- -1.0(홍보) ~ +1.0(감시)
    confidence    REAL NOT NULL DEFAULT 0.0,
    rationale     TEXT NOT NULL DEFAULT '',
    flagged_issues TEXT NOT NULL DEFAULT '[]',
    model         TEXT NOT NULL,
    classified_at TEXT NOT NULL
);

-- 사람이 직접 라벨링한 검증 셋. 이게 없으면 이 서비스는 공개하면 안 됩니다.
CREATE TABLE IF NOT EXISTS golden_labels (
    article_id  TEXT PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    category    TEXT NOT NULL,
    labeler     TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    labeled_at  TEXT NOT NULL
);

-- 실행 이력 (멱등 재실행 추적용)
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_date TEXT NOT NULL,
    stage       TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    stats       TEXT NOT NULL DEFAULT '{}',
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_date ON runs(target_date, stage);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    with connect(target) as c:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print(f"{target}\n  tables: {', '.join(tables)}")
