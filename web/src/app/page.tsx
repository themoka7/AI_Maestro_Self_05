import { ArticleInspector } from "@/components/ArticleInspector";
import { DailyTrend } from "@/components/DailyTrend";
import { DemoBanner } from "@/components/DemoBanner";
import { FramingDonut } from "@/components/FramingDonut";
import { Methodology } from "@/components/Methodology";
import { OutletTable } from "@/components/OutletTable";
import { Card, StatTile } from "@/components/StatTile";
import { loadDates, loadOutlets, loadSummary } from "@/lib/data";
import type { Category } from "@/lib/types";

function EmptyState() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-24">
      <h1 className="text-[20px] font-semibold">분석 데이터가 없습니다</h1>
      <p className="mt-3 text-[14px] leading-relaxed text-ink-2">
        파이프라인을 먼저 실행하세요. API 키가 아직 없다면 데모 데이터로 화면을 확인할 수 있습니다.
      </p>
      <pre className="mt-4 overflow-x-auto rounded-lg bg-surface p-4 text-[12px] leading-relaxed ring-1 ring-hairline">
{`# 실제 수집 (어제 하루치)
python pipeline/run.py

# 데모 데이터 3일치
for d in 2026-09-12 2026-09-13 2026-09-14; do
  python pipeline/seed_demo.py --date $d --with-mock-classification
  python pipeline/run.py --date $d --only dedup match export
done
python pipeline/aggregate.py`}
      </pre>
    </main>
  );
}

export default async function DashboardPage() {
  const [aggregate, summary, dates] = await Promise.all([
    loadOutlets(),
    loadSummary(),
    loadDates(),
  ]);
  if (!aggregate || !summary) return <EmptyState />;

  const { window, totals, outlets, params, event } = aggregate;
  const counts = summary.articles.reduce(
    (acc, a) => {
      if (a.category) acc[a.category] += 1;
      return acc;
    },
    { Watchdog: 0, Cheerleader: 0, Neutral: 0 } as Record<Category, number>
  );
  const ranked = outlets.filter((o) => o.sufficient_sample);
  const mostDependent = [...ranked].sort((a, b) => b.duplication_rate - a.duplication_rate)[0];

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
      {aggregate.demo && <DemoBanner />}

      <header>
        <p className="text-[12px] text-muted">
          {window.from} ~ {window.to} · {window.days}일 누적 · {event.name}
        </p>
        <h1 className="mt-1 text-[24px] font-semibold tracking-tight sm:text-[28px]">
          Parallax <span className="text-ink-2">— 보도 시차 분석</span>
        </h1>
        <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-ink-2">
          공식 보도자료를 기준점으로 두고, 각 언론사 보도가 그로부터 얼마나 떨어져 있는지
          잽니다. 거리가 0 에 가까우면 그대로 옮긴 것이고, 멀수록 자체 취재를 거친 것입니다.
        </p>
      </header>

      {/* 누적 헤드라인 — 하루치가 아니라 기간 전체 기준 */}
      <section className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="누적 분석 기사" value={totals.articles} unit="건"
                  note={`${window.days}일 · 언론사 ${outlets.length}곳`} />
        <StatTile label="보도자료 복제" value={totals.duplication_rate} unit="%"
                  accent="var(--dependent)" mark="▲"
                  note={`유사도 ${Math.round(params.duplication_threshold * 100)}% 이상`} />
        <StatTile label="자체 검증 보도" value={totals.watchdog_rate} unit="%"
                  accent="var(--watchdog)" mark="◆"
                  note="예산·안전·부실 취재" />
        <StatTile label="의존도 최상위" value={mostDependent?.outlet ?? "–"}
                  note={mostDependent
                    ? `복제율 ${mostDependent.duplication_rate}% · 기사 ${mostDependent.articles}건`
                    : `기사 ${params.min_articles}건 이상인 매체 없음`} />
      </section>

      {/* 언론사별 누적 판단 — 이 화면의 본체 */}
      <Card className="mt-6 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[14px] font-semibold">언론사별 누적 판단</h2>
          <p className="text-[12px] text-muted">
            일별 비율의 평균이 아니라 {window.days}일간 원시 건수를 합산한 값입니다.
          </p>
        </div>
        <div className="mt-4">
          <OutletTable outlets={outlets} minArticles={params.min_articles} />
        </div>
      </Card>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Card className="p-5 lg:col-span-3">
          <h2 className="text-[14px] font-semibold">날짜별 추이</h2>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            점 위에 올리면 그날의 수치를 봅니다.
          </p>
          <div className="mt-4">
            <DailyTrend daily={aggregate.daily} />
          </div>
        </Card>

        <Card className="p-5 lg:col-span-2">
          <h2 className="text-[14px] font-semibold">프레이밍 분포</h2>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            {summary.date} 하루치. 감시 ← 중립 → 홍보.
          </p>
          <div className="mt-5">
            <FramingDonut
              watchdog={summary.totals.watchdog_rate}
              neutral={summary.totals.neutral_rate}
              cheerleader={summary.totals.cheerleader_rate}
              counts={counts}
              total={summary.totals.articles}
            />
          </div>
        </Card>
      </div>

      <Card className="mt-4 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[14px] font-semibold">기사별 대조</h2>
          <p className="text-[12px] text-muted">
            {summary.date} 기준 (보유 {dates.length}일)
          </p>
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-muted">
          행을 누르면 기사와 보도자료를 문장 단위로 나란히 놓고, 그대로 옮긴 문장을 표시합니다.
        </p>
        <div className="mt-4">
          <ArticleInspector
            articles={summary.articles}
            threshold={params.duplication_threshold}
            date={summary.date}
          />
        </div>
      </Card>

      <div className="mt-4">
        <Methodology summary={summary} />
      </div>

      <footer className="mt-8 text-[11px] text-muted">
        생성 {new Date(aggregate.generatedAt).toLocaleString("ko-KR", {
          year: "numeric", month: "2-digit", day: "2-digit",
          hour: "2-digit", minute: "2-digit", hour12: false,
        })} · 기사 수집 NAVER API HUB · 분류 Claude
      </footer>
    </main>
  );
}
