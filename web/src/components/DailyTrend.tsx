"use client";

import { useState } from "react";
import type { Totals } from "@/lib/types";

type Point = Totals & { date: string };

const W = 640;
const H = 150;
const PAD = { top: 12, right: 12, bottom: 24, left: 34 };

/**
 * 날짜별 복제율·감시율 추이.
 *
 * 두 계열 모두 '전체 기사 대비 비율(%)' 이라 축을 공유합니다.
 * 축이 두 개인 차트는 만들지 않습니다 — 서로 다른 단위를 한 그림에 겹치면
 * 실제로는 없는 상관관계가 보입니다.
 */
export function DailyTrend({ daily }: { daily: Point[] }) {
  const [hover, setHover] = useState<number | null>(null);

  if (daily.length < 2) {
    return (
      <p className="py-6 text-center text-[12px] text-muted">
        추이를 그리려면 이틀 이상의 데이터가 필요합니다. 현재 {daily.length}일.
      </p>
    );
  }

  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (i / (daily.length - 1)) * innerW;
  const y = (v: number) => PAD.top + innerH - (v / 100) * innerH;

  const line = (key: "duplication_rate" | "watchdog_rate") =>
    daily.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d[key]).toFixed(1)}`).join(" ");

  const active = hover !== null ? daily[hover] : null;
  // 라벨이 겹치지 않도록 눈금은 최대 6개만 찍습니다.
  const step = Math.max(1, Math.ceil(daily.length / 6));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-[2px] w-4" style={{ background: "var(--dependent)" }} />
          <span className="text-ink-2">보도자료 복제율</span>
          {active && <span className="tabular font-medium">{active.duplication_rate}%</span>}
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-[2px] w-4" style={{ background: "var(--watchdog)" }} />
          <span className="text-ink-2">자체 검증 비율</span>
          {active && <span className="tabular font-medium">{active.watchdog_rate}%</span>}
        </span>
        <span className="ml-auto text-muted">
          {active ? `${active.date} · 기사 ${active.articles}건` : `${daily.length}일`}
        </span>
      </div>

      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[420px]" role="img"
             aria-label="날짜별 보도자료 복제율과 자체 검증 비율 추이"
             onMouseLeave={() => setHover(null)}>
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)}
                    stroke="var(--gridline)" strokeWidth={1} />
              <text x={PAD.left - 6} y={y(v) + 3} textAnchor="end"
                    fill="var(--text-muted)" fontSize={9}>{v}</text>
            </g>
          ))}

          {daily.map((d, i) =>
            i % step === 0 || i === daily.length - 1 ? (
              <text key={d.date} x={x(i)} y={H - 6} textAnchor="middle"
                    fill="var(--text-muted)" fontSize={9}>{d.date.slice(5)}</text>
            ) : null
          )}

          {hover !== null && (
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH}
                  stroke="var(--baseline)" strokeWidth={1} />
          )}

          <path d={line("duplication_rate")} fill="none" stroke="var(--dependent)"
                strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
          <path d={line("watchdog_rate")} fill="none" stroke="var(--watchdog)"
                strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />

          {hover !== null && (
            <>
              {/* 표면 링을 둘러 겹치는 마크가 서로 묻히지 않게 합니다 */}
              <circle cx={x(hover)} cy={y(daily[hover].duplication_rate)} r={4.5}
                      fill="var(--dependent)" stroke="var(--surface-1)" strokeWidth={2} />
              <circle cx={x(hover)} cy={y(daily[hover].watchdog_rate)} r={4.5}
                      fill="var(--watchdog)" stroke="var(--surface-1)" strokeWidth={2} />
            </>
          )}

          {/* 마크보다 넉넉한 히트 영역 */}
          {daily.map((d, i) => (
            <rect key={d.date} x={x(i) - innerW / (daily.length - 1) / 2} y={PAD.top}
                  width={innerW / (daily.length - 1)} height={innerH}
                  fill="transparent" onMouseEnter={() => setHover(i)} />
          ))}
        </svg>
      </div>
    </div>
  );
}
