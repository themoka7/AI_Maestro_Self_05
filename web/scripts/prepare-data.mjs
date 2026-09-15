/**
 * data/history → web/public/data 복사.
 *
 * 정적 export 에서는 서버가 없어 파일시스템을 런타임에 읽을 수 없습니다.
 * 빌드 시점에 한 번 읽는 것(페이지 생성)과, 브라우저가 나중에 가져가는 것(대조 상세)을
 * 구분해야 하며, 후자는 public/ 에 있어야 합니다.
 */
import { cp, mkdir, rm, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const history = path.join(here, "..", "..", "data", "history");
const target = path.join(here, "..", "public", "data");

try {
  await access(history);
} catch {
  console.warn(`[prepare-data] ${history} 가 없습니다. 파이프라인을 먼저 실행하세요.`);
  process.exit(0);
}

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(history, target, { recursive: true });
console.log(`[prepare-data] ${history} → ${target}`);
