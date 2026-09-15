import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    // 그림자 없이 헤어라인만. 실루엣 사진처럼 경계가 단단해야 합니다.
    <div className={`rounded-[3px] bg-surface ring-1 ring-hairline ${className}`}>
      {children}
    </div>
  );
}

export function StatTile({
  label, value, unit, note, accent, mark,
}: {
  label: string;
  value: string | number;
  unit?: string;
  note?: string;
  accent?: string;
  mark?: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-1.5 text-[12px] uppercase tracking-wide text-muted">
        {accent && (
          <span aria-hidden className="text-[11px] leading-none" style={{ color: accent }}>
            {mark ?? "●"}
          </span>
        )}
        <span>{label}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="tabular text-[34px] font-semibold leading-none tracking-tight">
          {value}
        </span>
        {unit && <span className="text-[15px] text-ink-2">{unit}</span>}
      </div>
      {note && <p className="mt-2 text-[12px] leading-snug text-muted">{note}</p>}
    </Card>
  );
}
