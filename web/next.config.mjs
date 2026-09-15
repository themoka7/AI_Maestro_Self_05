/**
 * GitHub Pages 배포용 정적 export 설정.
 *
 * Pages 는 정적 호스팅이라 서버 런타임이 없습니다. 그래서:
 *   - output: "export"  → 빌드 시 HTML/JSON 을 전부 뽑아냅니다 (API 라우트 사용 불가).
 *   - basePath          → 프로젝트 페이지는 /<repo> 하위에 올라가므로 경로 접두사가 필요합니다.
 *   - images.unoptimized→ 정적 export 에서는 이미지 최적화 서버가 없습니다.
 *
 * 기사 대조 상세는 런타임에 fetch 하므로 data/history/details 를 public/ 으로 복사해
 * 정적 파일로 서빙합니다 (scripts/prepare-data.mjs, prebuild 에서 실행).
 */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default nextConfig;
