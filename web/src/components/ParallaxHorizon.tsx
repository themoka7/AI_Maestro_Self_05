"use client";

import { useEffect, useState } from "react";
import type { OutletCumulative } from "@/lib/types";

/**
 * 시차 지평선 — 이 서비스의 은유를 그대로 그린 도형.
 *
 * 지평선은 공식 보도자료라는 기준점입니다. 각 언론사는 그 선 위에 서 있고,
 * 선에서 떠오른 높이가 기준점으로부터의 거리(자율성 점수)입니다.
 * 선에 붙어 있으면 보도자료를 그대로 옮긴 것이고, 높이 뛴 것은 자체 취재를 거친 것입니다.
 *
 * 장식이 아니라 실제 지표를 읽는 도형입니다. 막대(스템)와 끝점(도트)은 기준선에
 * 앵커된 롤리팝 형태이며, 아래 표가 같은 데이터의 표 형태 보기가 됩니다.
 */

/**
 * 좁은 화면에서는 뷰박스 자체를 좁힙니다.
 * 같은 뷰박스를 축소하면 글자까지 같이 줄어 4px 로 뭉개집니다. 뷰박스를 좁히면
 * 화면 폭에 대한 배율이 올라가 글자가 읽히는 크기로 렌더됩니다.
 */
const WIDE = { W: 1000, H: 300, horizon: 232, padX: 56, rise: 168, label: 11, axis: 9, max: 12 };
const NARROW = { W: 420, H: 260, horizon: 196, padX: 48, rise: 140, label: 11, axis: 8, max: 6 };

function useNarrow(): boolean {
  // 정적 export 는 서버에서 먼저 그려지므로 넓은 화면을 기본값으로 두고
  // 마운트 후 실제 폭에 맞춥니다.
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    const sync = () => setNarrow(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return narrow;
}

/**
 * 기준선으로부터의 거리.
 *
 * 분류(Anthropic 키)가 있으면 자율성 점수를 씁니다. 없으면 100 − 복제율을 씁니다 —
 * 보도자료를 그대로 옮길수록 기준선에 붙는다는 뜻이라 은유가 그대로 성립하고,
 * 복제율은 순수 텍스트 비교라 키 없이도 항상 계산됩니다.
 */
function distance(o: OutletCumulative): number {
  return o.autonomy_score ?? Math.max(0, 100 - o.duplication_rate);
}

export function ParallaxHorizon({
  outlets, hasClassification,
}: {
  outlets: OutletCumulative[];
  hasClassification: boolean;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const narrow = useNarrow();
  const { W, H, horizon: HORIZON, padX: PAD_X, rise: MAX_RISE, label, axis, max } =
    narrow ? NARROW : WIDE;

  const shown = outlets.filter((o) => o.sufficient_sample).slice(0, max);
  if (shown.length === 0) return null;

  const step = shown.length > 1 ? (W - PAD_X * 2) / (shown.length - 1) : 0;
  const placed = shown.map((o, i) => ({
    ...o,
    x: shown.length > 1 ? PAD_X + i * step : W / 2,
    y: HORIZON - (distance(o) / 100) * MAX_RISE,
  }));

  const highest = placed.reduce((a, b) => (distance(b) > distance(a) ? b : a));
  const active = hover ? placed.find((p) => p.outlet === hover) : null;

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="block w-full"
        role="img"
        aria-label={
          `보도자료 기준선으로부터의 거리. ` +
          placed.map((p) => `${p.outlet} ${distance(p).toFixed(0)}`).join(", ")
        }
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--sky-top)" />
            <stop offset="100%" stopColor="var(--sky-bottom)" />
          </linearGradient>
        </defs>

        <rect x="0" y="0" width={W} height={HORIZON} fill="url(#sky)" />

        {/* 기준선 위 눈금 — 거리를 읽을 수 있게 하되 배경으로 물러납니다 */}
        {[25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line
              x1={PAD_X - 4} x2={W - PAD_X + 16}
              y1={HORIZON - (v / 100) * MAX_RISE} y2={HORIZON - (v / 100) * MAX_RISE}
              stroke="var(--horizon-grid)" strokeWidth={1}
            />
            <text
              x={PAD_X - 8} y={HORIZON - (v / 100) * MAX_RISE + 3}
              textAnchor="end" fontSize={axis} fill="var(--horizon-muted)"
            >
              {v}
            </text>
          </g>
        ))}

        {placed.map((p) => {
          const on = hover === p.outlet;
          const isTop = p.outlet === highest.outlet;
          return (
            <g key={p.outlet}
               onMouseEnter={() => setHover(p.outlet)}
               className="cursor-pointer">
              {/* 히트 영역은 마크보다 넉넉하게 */}
              <rect x={p.x - step / 2} y={0} width={Math.max(step, 44)} height={HORIZON}
                    fill="transparent" />
              <line x1={p.x} x2={p.x} y1={HORIZON} y2={p.y}
                    stroke={on || isTop ? "var(--watchdog)" : "var(--horizon-stem)"}
                    strokeWidth={2} strokeLinecap="round" />
              <circle cx={p.x} cy={p.y} r={on ? 7 : isTop ? 6 : 5}
                      fill={on || isTop ? "var(--watchdog)" : "var(--horizon-mark)"}
                      stroke="var(--sky-bottom)" strokeWidth={2} />
              {/* 직접 라벨은 넓은 화면에서만. 좁으면 호버와 아래 표로 읽습니다. */}
              <text x={p.x} y={p.y - 13} textAnchor="middle" fontSize={label}
                    fill={on || isTop ? "var(--text-primary)" : "var(--horizon-label)"}
                    fontWeight={on || isTop ? 600 : 400}>
                {p.outlet}
              </text>
            </g>
          );
        })}

        {/* 땅 — 보도자료 기준점. 가장자리에 얇은 빛을 둬 경계를 또렷하게 유지합니다. */}
        <rect x="0" y={HORIZON} width={W} height={H - HORIZON} fill="var(--ground)" />
        <line x1="0" x2={W} y1={HORIZON + 0.5} y2={HORIZON + 0.5}
              stroke="var(--horizon-edge)" strokeWidth={1} />
        <text x={PAD_X - 8} y={HORIZON + 22} fontSize={label} fill="var(--ground-text)">
          기준선 · 공식 보도자료
        </text>
        {!narrow && (
          <text x={W - PAD_X + 16} y={HORIZON + 22} textAnchor="end" fontSize={label}
                fill="var(--ground-text)">
            선에 붙을수록 그대로 옮긴 보도
          </text>
        )}
      </svg>

      {/* 캡션은 땅 위에 놓습니다. 검은 띠에서 밝은 배경으로 끊기면 지면이 아니라
          한낱 가로줄로 읽힙니다. */}
      <figcaption
        className="-mt-px"
        style={{ background: "var(--ground)", color: "var(--ground-text)" }}
      >
        <div className="mx-auto max-w-6xl px-4 pb-7 pt-1 text-[12px] leading-relaxed sm:px-6">
          {active ? (
            <span>
              <b style={{ color: "#fff" }}>{active.outlet}</b> · 기준선에서{" "}
              <b style={{ color: "#fff" }}>{distance(active).toFixed(1)}</b> 만큼 떨어짐 ·
              복제율 {active.duplication_rate}%
              {active.watchdog_rate !== null && ` · 감시 보도 ${active.watchdog_rate}%`} ·
              기사 {active.articles}건 / {active.activeDays}일
            </span>
          ) : (
            <span>
              지평선은 공식 보도자료입니다. 각 매체가 그 선에서 얼마나 떠올랐는지가
              자체 취재의 거리이며, 가장 높이 오른 곳은{" "}
              <b style={{ color: "#fff" }}>{highest.outlet}</b>
              ({distance(highest).toFixed(1)})입니다.
              {!hasClassification && " 분류가 없어 복제율만으로 거리를 잡았습니다."}
              {" "}점 위에 올리면 세부 수치를 봅니다.
            </span>
          )}
        </div>
      </figcaption>
    </figure>
  );
}
