import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import type { Detail, OutletAggregate, Summary } from "./types";

// 파이프라인(pipeline/export.py, aggregate.py)이 떨군 JSON 을 읽습니다.
// data/history/ 가 리포지토리에 커밋되는 단일 저장소이고, SQLite 는 실행마다 재구성됩니다.
// GitHub Actions 러너는 매번 초기화되므로 DB 를 신뢰할 수 없습니다.
const HISTORY = path.join(process.cwd(), "..", "data", "history");

async function readJson<T>(...segments: string[]): Promise<T | null> {
  try {
    return JSON.parse(await readFile(path.join(HISTORY, ...segments), "utf-8")) as T;
  } catch {
    return null;
  }
}

/** 보유한 날짜 목록 (최신순). index.json 이 없으면 디렉터리를 직접 훑습니다. */
export async function loadDates(): Promise<string[]> {
  const idx = await readJson<{ dates: string[] }>("index.json");
  if (idx?.dates?.length) return [...idx.dates].reverse();
  try {
    const files = await readdir(path.join(HISTORY, "daily"));
    return files.filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5)).sort().reverse();
  } catch {
    return [];
  }
}

/** 특정 날짜의 일별 결과. date 를 생략하면 가장 최근 날짜. */
export async function loadSummary(date?: string): Promise<Summary | null> {
  const target = date ?? (await loadDates())[0];
  if (!target) return null;
  return readJson<Summary>("daily", `${target}.json`);
}

/** 날짜를 가로지르는 언론사별 누적 집계. 이 화면의 본체입니다. */
export async function loadOutlets(): Promise<OutletAggregate | null> {
  return readJson<OutletAggregate>("outlets.json");
}

export async function loadDetail(date: string, articleId: string): Promise<Detail | null> {
  // 경로 조작 방지: 날짜와 기사 id 형식을 고정합니다.
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  if (!/^[a-f0-9]{16}$/.test(articleId)) return null;
  return readJson<Detail>("details", date, `${articleId}.json`);
}
