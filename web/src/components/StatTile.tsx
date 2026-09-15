import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-lg bg-surface ring-1 ring-hairline ${className}`}
      style={{ boxShadow: "0 1px 2px rgba(0,0,0,0.04)" }}
    >
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
      <div className="flex items-center gap-1.5 text-[13px] text-ink-2">
        {accent && (
          <span aria-hidden className="text-[11px] leading-none" style={{ color: accent }}>
            {mark ?? "●"}
          </span>
        )}
        <span>{label}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="tabular text-[32px] font-semibold leading-none tracking-tight">
          {value}
        </span>
        {unit && <span className="text-[15px] text-ink-2">{unit}</span>}
      </div>
      {note && <p className="mt-2 text-[12px] leading-snug text-muted">{note}</p>}
    </Card>
  );
}
