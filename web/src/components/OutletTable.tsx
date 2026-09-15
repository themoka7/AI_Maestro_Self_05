"use client";

import { useState } from "react";
import type { Outlet, OutletCumulative } from "@/lib/types";

type SortKey = "autonomy_score" | "duplication_rate" | "watchdog_rate" | "articles";

/** 값 끝이 4px 둥근 얇은 막대. 기준선(0)에 앵커되고 트랙 위에 얹힙니다. */
function Bar({ pct, color, width = 72 }: { pct: number; color: string; width?: number }) {
  const w = Math.max(0, Math.min(100, pct));
  return (
    <span className="inline-flex items-center gap-2">
      <span className="relative block h-[8px] shrink-0 rounded-full"
            style={{ width, background: "var(--track)" }}>
        <span className="absolute left-0 top-0 h-full rounded-full"
              style={{ width: `${w}%`, background: color }} />
      </span>
      <span className="tabular w-11 text-right text-[12px] text-ink-2">{pct.toFixed(1)}</span>
    </span>
  );
}

function isCumulative(o: Outlet | OutletCumulative): o is OutletCumulative {
  return "activeDays" in o;
}

/** 추세는 색만으로 방향을 나타내지 않도록 화살표를 함께 씁니다. */
function Trend({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">–</span>;
  if (Math.abs(value) < 0.5) return <span className="tabular text-muted">0.0</span>;
  const up = value > 0;
  return (
    <span className="tabular whitespace-nowrap"
          style={{ color: up ? "var(--watchdog)" : "var(--dependent)" }}>
      {up ? "↑" : "↓"} {Math.abs(value).toFixed(1)}
    </span>
  );
}

export function OutletTable({
  outlets, minArticles,
}: { outlets: (Outlet | OutletCumulative)[]; minArticles: number }) {
  const [sort, setSort] = useState<SortKey>("autonomy_score");
  const [showAll, setShowAll] = useState(false);
  const cumulative = outlets.some(isCumulative);

  const ranked = outlets.filter((o) => o.sufficient_sample);
  const insufficient = outlets.filter((o) => !o.sufficient_sample);
  const shown = [...(showAll ? [...ranked, ...insufficient] : ranked)].sort(
    (a, b) => (b[sort] as number) - (a[sort] as number)
  );

  const header = (key: SortKey, label: string, hint?: string) => (
    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">
      <button
        onClick={() => setSort(key)}
        title={hint}
        className={`inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-plane ${
          sort === key ? "text-ink" : "text-ink-2"
        }`}
      >
        {label}
        <span aria-hidden className={sort === key ? "opacity-100" : "opacity-0"}>↓</span>
      </button>
    </th>
  );

  return (
    <div>
      <div className="overflow-x-auto">
        <table className={`w-full border-collapse text-[13px] ${cumulative ? "min-w-[700px]" : "min-w-[560px]"}`}>
          <thead>
            <tr className="border-b text-ink-2" style={{ borderColor: "var(--gridline)" }}>
              <th scope="col" className="px-2 py-2 text-left font-medium w-8">#</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">언론사</th>
              {header("articles", "기사")}
              {cumulative && (
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">
                  보도일
                </th>
              )}
              {header("autonomy_score", "자율성", "0~100. 표본 보정 후 값")}
              {header("duplication_rate", "복제율", "보도자료와 유사도가 임계값 이상인 기사 비율")}
              {header("watchdog_rate", "감시%", "자체 검증 보도 비율")}
              {cumulative && (
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium"
                    title="최근 7일 평균 자율성 점수 − 그 이전 평균">
                  추세
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {shown.map((o, i) => (
              <tr key={o.outlet} className="border-b last:border-0"
                  style={{ borderColor: "var(--gridline)" }}>
                <td className="tabular px-2 py-2.5 text-muted">
                  {o.sufficient_sample ? i + 1 : "–"}
                </td>
                <td className="px-3 py-2.5">
                  <span className="font-medium">{o.outlet}</span>
                  {!o.sufficient_sample && (
                    <span className="ml-2 rounded px-1.5 py-0.5 text-[11px] text-muted"
                          style={{ background: "var(--plane)" }}>
                      표본 {o.articles}건
                    </span>
                  )}
                </td>
                <td className="tabular px-3 py-2.5 text-right text-ink-2">{o.articles}</td>
                {cumulative && (
                  <td className="tabular px-3 py-2.5 text-right text-muted">
                    {isCumulative(o) ? o.activeDays : "–"}
                  </td>
                )}
                <td className="px-3 py-2.5 text-right">
                  <Bar pct={o.autonomy_score} color="var(--watchdog)" />
                </td>
                <td className="px-3 py-2.5 text-right">
                  <Bar pct={o.duplication_rate} color="var(--dependent)" />
                </td>
                <td className="tabular px-3 py-2.5 text-right text-ink-2">
                  {o.watchdog_rate.toFixed(1)}%
                </td>
                {cumulative && (
                  <td className="px-3 py-2.5 text-right text-[12px]">
                    <Trend value={isCumulative(o) ? o.trend : null} />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {insufficient.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-muted">
          <span>
            기사 {minArticles}건 미만 {insufficient.length}곳은 표본 부족으로 순위에서 제외했습니다.
          </span>
          <button onClick={() => setShowAll((v) => !v)}
                  className="rounded px-2 py-0.5 ring-1 ring-hairline hover:bg-plane">
            {showAll ? "숨기기" : "함께 보기"}
          </button>
        </div>
      )}
    </div>
  );
}
