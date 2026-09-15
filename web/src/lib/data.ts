import { readFile } from "node:fs/promises";
import path from "node:path";
import type { Detail, Summary } from "./types";

// 파이프라인(pipeline/export.py)이 떨군 JSON 을 읽습니다.
// SQLite 를 직접 읽지 않는 이유는 네이티브 모듈 빌드를 피하고, 나중에 DB 를 바꿔도
// 이 JSON 계약만 지키면 프런트를 건드릴 필요가 없게 하기 위함입니다.
const DATA_DIR = path.join(process.cwd(), "data");

export async function loadSummary(): Promise<Summary | null> {
  try {
    const raw = await readFile(path.join(DATA_DIR, "latest.json"), "utf-8");
    return JSON.parse(raw) as Summary;
  } catch {
    return null;
  }
}

export async function loadDetail(articleId: string): Promise<Detail | null> {
  // 경로 조작 방지: 파이프라인이 만드는 id 는 16자리 hex 입니다.
  if (!/^[a-f0-9]{16}$/.test(articleId)) return null;
  try {
    const raw = await readFile(path.join(DATA_DIR, "details", `${articleId}.json`), "utf-8");
    return JSON.parse(raw) as Detail;
  } catch {
    return null;
  }
}
