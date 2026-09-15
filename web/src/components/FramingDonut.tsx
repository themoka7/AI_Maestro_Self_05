"use client";

import { useState } from "react";
import { CATEGORY_LABEL, CATEGORY_MARK, CATEGORY_VAR, type Category } from "@/lib/types";

const R = 62;
const STROKE = 26;
const CIRC = 2 * Math.PI * R;
const GAP = 2; // 인접 조각 사이 2px 표면 간격

type Slice = { key: Category; value: number; count: number };

export function FramingDonut({
  watchdog, neutral, cheerleader, counts, total,
}: {
  watchdog: number;
  neutral: number;
  cheerleader: number;
  counts: Record<Category, number>;
  total: number;
}) {
  const [hover, setHover] = useState<Category | null>(null);

  // 발산형 순서로 배치: 감시 → 중립 → 의존
  const slices: Slice[] = [
    { key: "Watchdog", value: watchdog, count: counts.Watchdog },
    { key: "Neutral", value: neutral, count: counts.Neutral },
    { key: "Cheerleader", value: cheerleader, count: counts.Cheerleader },
  ];

  let acc = 0;
  const arcs = slices.map((s) => {
    const len = (s.value / 100) * CIRC;
    const arc = { ...s, len, offset: acc, mid: acc + len / 2 };
    acc += len;
    return arc;
  });

  const active = hover ? arcs.find((a) => a.key === hover) : null;

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
      <div className="relative shrink-0">
        <svg width={168} height={168} viewBox="0 0 168 168" role="img"
             aria-label={`보도 프레이밍 분포: 감시 ${watchdog}%, 중립 ${neutral}%, 홍보 ${cheerleader}%`}>
          <g transform="translate(84,84) rotate(-90)">
            <circle r={R} fill="none" stroke="var(--track)" strokeWidth={STROKE} />
            {arcs.map((a) => (
              <circle
                key={a.key}
                r={R}
                fill="none"
                stroke={CATEGORY_VAR[a.key]}
                strokeWidth={hover === a.key ? STROKE + 4 : STROKE}
                strokeDasharray={`${Math.max(a.len - GAP, 0)} ${CIRC - Math.max(a.len - GAP, 0)}`}
                strokeDashoffset={-a.offset}
                className="cursor-pointer transition-[stroke-width] duration-150"
                onMouseEnter={() => setHover(a.key)}
                onMouseLeave={() => setHover(null)}
              />
            ))}
          </g>
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          {active ? (
            <>
              <span className="tabular text-[22px] font-semibold leading-none"
                    style={{ color: CATEGORY_VAR[active.key] }}>
                {active.value}%
              </span>
              <span className="mt-1 text-[11px] text-ink-2">
                {CATEGORY_LABEL[active.key]} {active.count}건
              </span>
            </>
          ) : (
            <>
              <span className="tabular text-[22px] font-semibold leading-none">{total}</span>
              <span className="mt-1 text-[11px] text-muted">분석 기사</span>
            </>
          )}
        </div>
      </div>

      {/* 범례 — 색만으로 구분되지 않도록 기호와 수치를 함께 둡니다 */}
      <ul className="w-full space-y-2">
        {arcs.map((a) => (
          <li
            key={a.key}
            className="flex items-center gap-2 rounded px-2 py-1 text-[13px] transition-colors"
            style={{ background: hover === a.key ? "var(--plane)" : "transparent" }}
            onMouseEnter={() => setHover(a.key)}
            onMouseLeave={() => setHover(null)}
          >
            <span aria-hidden className="text-[10px] leading-none"
                  style={{ color: CATEGORY_VAR[a.key] }}>
              {CATEGORY_MARK[a.key]}
            </span>
            <span className="text-ink-2">{CATEGORY_LABEL[a.key]}</span>
            <span className="tabular ml-auto font-medium">{a.value}%</span>
            <span className="tabular w-12 text-right text-muted">{a.count}건</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
