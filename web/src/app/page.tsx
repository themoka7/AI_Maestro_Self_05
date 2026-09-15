import { ArticleInspector } from "@/components/ArticleInspector";
import { FramingDonut } from "@/components/FramingDonut";
import { Methodology } from "@/components/Methodology";
import { OutletTable } from "@/components/OutletTable";
import { Card, StatTile } from "@/components/StatTile";
import { loadSummary } from "@/lib/data";
import type { Category } from "@/lib/types";

export const dynamic = "force-dynamic";

function EmptyState() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-24">
      <h1 className="text-[20px] font-semibold">분석 데이터가 없습니다</h1>
      <p className="mt-3 text-[14px] leading-relaxed text-ink-2">
        파이프라인을 먼저 실행하세요. 네이버 API 키가 아직 없다면 데모 데이터로 화면을 확인할 수 있습니다.
      </p>
      <pre className="mt-4 overflow-x-auto rounded-lg bg-surface p-4 text-[12px] leading-relaxed ring-1 ring-hairline">
{`# 실제 수집
python pipeline/run.py --date 2026-09-14

# 데모 데이터
python pipeline/seed_demo.py --date 2026-09-14 --reset --with-mock-classification
python pipeline/run.py --date 2026-09-14 --only dedup match export`}
      </pre>
    </main>
  );
}

export default async function DashboardPage() {
  const summary = await loadSummary();
  if (!summary) return <EmptyState />;

  const { totals, outlets, articles, params, event } = summary;
  const counts = articles.reduce(
    (acc, a) => {
      if (a.category) acc[a.category] += 1;
      return acc;
    },
    { Watchdog: 0, Cheerleader: 0, Neutral: 0 } as Record<Category, number>
  );
  const duplicatedCount = articles.filter((a) => a.isDuplicated).length;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
      <header>
        <p className="text-[12px] text-muted">
          {summary.date} 보도 · {event.name}
        </p>
        <h1 className="mt-1 text-[24px] font-semibold tracking-tight sm:text-[28px]">
          보도 공정성 &amp; 보도자료 의존도 분석
        </h1>
        <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-ink-2">
          {event.description}
        </p>
      </header>

      {/* 헤드라인 수치 */}
      <section className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="분석 기사" value={totals.articles} unit="건"
                  note={`고유 기사 ${summary.totalsUniqueOnly.articles}건 · 언론사 ${outlets.length}곳`} />
        <StatTile label="보도자료 복제" value={totals.duplication_rate} unit="%"
                  accent="var(--dependent)" mark="▲"
                  note={`유사도 ${Math.round(params.duplication_threshold * 100)}% 이상 ${duplicatedCount}건`} />
        <StatTile label="자체 검증 보도" value={totals.watchdog_rate} unit="%"
                  accent="var(--watchdog)" mark="◆"
                  note={`예산·안전·부실 취재 ${counts.Watchdog}건`} />
        <StatTile label="단순 홍보 보도" value={totals.cheerleader_rate} unit="%"
                  accent="var(--dependent)" mark="▲"
                  note={`발표 일방 전달 ${counts.Cheerleader}건`} />
      </section>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Card className="p-5 lg:col-span-2">
          <h2 className="text-[14px] font-semibold">보도 프레이밍 분포</h2>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            감시 ← 중립 → 홍보. 양 끝이 반대 성격입니다.
          </p>
          <div className="mt-5">
            <FramingDonut
              watchdog={totals.watchdog_rate}
              neutral={totals.neutral_rate}
              cheerleader={totals.cheerleader_rate}
              counts={counts}
              total={totals.articles}
            />
          </div>
        </Card>

        <Card className="p-5 lg:col-span-3">
          <h2 className="text-[14px] font-semibold">언론사별 자율성 순위</h2>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            열 제목을 눌러 정렬을 바꿀 수 있습니다.
          </p>
          <div className="mt-4">
            <OutletTable outlets={outlets} minArticles={params.min_articles} />
          </div>
        </Card>
      </div>

      <Card className="mt-4 p-5">
        <h2 className="text-[14px] font-semibold">기사별 대조</h2>
        <p className="mt-1 text-[12px] leading-relaxed text-muted">
          행을 누르면 기사와 보도자료를 문장 단위로 나란히 놓고, 그대로 옮긴 문장을 표시합니다.
        </p>
        <div className="mt-4">
          <ArticleInspector articles={articles} threshold={params.duplication_threshold} />
        </div>
      </Card>

      <div className="mt-4">
        <Methodology summary={summary} />
      </div>

      <footer className="mt-8 text-[11px] text-muted">
        생성 {new Date(summary.generatedAt).toLocaleString("ko-KR", {
          year: "numeric", month: "2-digit", day: "2-digit",
          hour: "2-digit", minute: "2-digit", hour12: false,
        })} ·
        기사 수집 네이버 검색 API · 분류 Claude
      </footer>
    </main>
  );
}
