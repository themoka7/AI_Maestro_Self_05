import { ArticleInspector } from "@/components/ArticleInspector";
import { DailyTrend } from "@/components/DailyTrend";
import { DemoBanner } from "@/components/DemoBanner";
import { FramingDonut } from "@/components/FramingDonut";
import { Methodology } from "@/components/Methodology";
import { OutletTable } from "@/components/OutletTable";
import { ParallaxHorizon } from "@/components/ParallaxHorizon";
import { Card, StatTile } from "@/components/StatTile";
import { loadDates, loadOutlets, loadSummary } from "@/lib/data";
import type { Category } from "@/lib/types";

function Section({
  title, note, children, className = "",
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={`p-5 ${className}`}>
      {/* 제목마다 얇은 기준선 — 지평선 모티프가 페이지 전체에서 반복됩니다 */}
      <div className="rule-top flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[13px] font-semibold uppercase tracking-wide">{title}</h2>
        {note && <p className="text-[12px] text-muted">{note}</p>}
      </div>
      <div className="mt-5">{children}</div>
    </Card>
  );
}

function EmptyState() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-24">
      <h1 className="text-[20px] font-semibold">분석 데이터가 없습니다</h1>
      <p className="mt-3 text-[14px] leading-relaxed text-ink-2">
        파이프라인을 먼저 실행하세요. API 키가 아직 없다면 데모 데이터로 화면을 확인할 수 있습니다.
      </p>
      <pre className="mt-4 overflow-x-auto rounded-[3px] bg-surface p-4 text-[12px] leading-relaxed ring-1 ring-hairline">
{`python pipeline/run.py          # 어제 하루치
python pipeline/aggregate.py    # 누적 집계`}
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
    <main>
      {/* 히어로 = 지평선. 제목은 하늘에 있고, 각 매체는 기준선 위에 서 있습니다. */}
      <section style={{ background: "var(--sky-top)" }}>
        <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6 sm:pt-14">
          {aggregate.demo && <DemoBanner />}

          <p className="text-[12px] tracking-wide text-muted">
            {window.from} — {window.to} · {window.days}일 누적 · {event.name}
          </p>
          <h1 className="mt-3 text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] sm:text-[52px]">
            Parallax
          </h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-2">
            같은 사건도 보는 위치에 따라 달라 보입니다.{" "}
            <br className="hidden sm:inline" />
            공식 보도자료를 기준점에 두고, 각 언론사가 그 선에서 얼마나 떨어져 있는지 잽니다.
          </p>
          {!aggregate.hasClassification && (
            <p className="mt-3 max-w-2xl text-[12px] leading-relaxed text-muted">
              프레이밍 분류가 아직 없어 거리는 <b>복제율만으로</b> 잡았습니다.
              보도자료를 그대로 옮길수록 기준선에 붙습니다.
            </p>
          )}
        </div>

        <div className="mt-10">
          <ParallaxHorizon outlets={outlets} hasClassification={aggregate.hasClassification} />
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        <section className="-mt-px grid grid-cols-1 gap-3 pt-8 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="누적 기사" value={totals.articles} unit="건"
                    note={`${window.days}일 · 언론사 ${outlets.length}곳`} />
          <StatTile label="보도자료 복제" value={totals.duplication_rate} unit="%"
                    accent="var(--dependent)" mark="▲"
                    note={`유사도 ${Math.round(params.duplication_threshold * 100)}% 이상`} />
          {totals.watchdog_rate === null ? (
            <StatTile label="자체 검증" value="–"
                      note="분류 미수행 · ANTHROPIC_API_KEY 필요" />
          ) : (
            <StatTile label="자체 검증" value={totals.watchdog_rate} unit="%"
                      accent="var(--watchdog)" mark="◆"
                      note="예산·안전·부실 취재" />
          )}
          <StatTile label="기준선에 가장 가까운 곳" value={mostDependent?.outlet ?? "–"}
                    note={mostDependent
                      ? `복제율 ${mostDependent.duplication_rate}% · 기사 ${mostDependent.articles}건`
                      : `기사 ${params.min_articles}건 이상인 매체 없음`} />
        </section>

        <div className="mt-4">
          <Section title="언론사별 누적 판단"
                   note={`일별 비율의 평균이 아니라 ${window.days}일간 원시 건수 합산`}>
            <OutletTable outlets={outlets} minArticles={params.min_articles} />
          </Section>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-5">
          <Section title="날짜별 추이" note="점 위에 올리면 그날의 수치" className="lg:col-span-3">
            <DailyTrend daily={aggregate.daily} />
          </Section>
          <Section title="프레이밍 분포" note={`${summary.date} 하루치`} className="lg:col-span-2">
            {summary.totals.watchdog_rate === null ? (
              <p className="py-8 text-center text-[12px] leading-relaxed text-muted">
                분류 결과가 없습니다.
                <br />
                <code>ANTHROPIC_API_KEY</code> 를 설정하면 감시·홍보·중립 분포가 표시됩니다.
                <br />
                복제율 지표는 키 없이도 계산됩니다.
              </p>
            ) : (
              <FramingDonut
                watchdog={summary.totals.watchdog_rate}
                neutral={summary.totals.neutral_rate ?? 0}
                cheerleader={summary.totals.cheerleader_rate ?? 0}
                counts={counts}
                total={summary.totals.articles}
              />
            )}
          </Section>
        </div>

        <div className="mt-4">
          <Section title="기사별 대조" note={`${summary.date} 기준 · 보유 ${dates.length}일`}>
            <p className="-mt-2 mb-4 text-[12px] leading-relaxed text-muted">
              행을 누르면 기사와 보도자료를 문장 단위로 나란히 놓고, 그대로 옮긴 문장을 표시합니다.
            </p>
            <ArticleInspector
              articles={summary.articles}
              threshold={params.duplication_threshold}
              date={summary.date}
            />
          </Section>
        </div>

        <div className="mt-4">
          <Methodology summary={summary} />
        </div>

        <footer className="mt-10 border-t pt-4 text-[11px] text-muted"
                style={{ borderColor: "var(--gridline)" }}>
          생성 {new Date(aggregate.generatedAt).toLocaleString("ko-KR", {
            year: "numeric", month: "2-digit", day: "2-digit",
            hour: "2-digit", minute: "2-digit", hour12: false,
          })} · 기사 수집 NAVER API HUB · 분류 Claude
        </footer>
      </div>
    </main>
  );
}
