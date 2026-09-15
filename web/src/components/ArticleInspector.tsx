"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CATEGORY_LABEL, CATEGORY_MARK, CATEGORY_VAR,
  type Article, type Category, type Detail,
} from "@/lib/types";

function CategoryBadge({ category }: { category: Category | null }) {
  if (!category) {
    return <span className="text-[12px] text-muted">미분류</span>;
  }
  // 색 + 기호 + 라벨을 함께 둡니다. 색만으로 의미를 전달하지 않습니다.
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-[12px]">
      <span aria-hidden className="text-[10px] leading-none" style={{ color: CATEGORY_VAR[category] }}>
        {CATEGORY_MARK[category]}
      </span>
      <span className="text-ink-2">{CATEGORY_LABEL[category]}</span>
    </span>
  );
}

// 정적 export 에는 서버 런타임이 없으므로 대조 상세는 public/ 의 정적 JSON 으로 가져옵니다.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

function DiffModal({
  article, date, onClose,
}: { article: Article; date: string; onClose: () => void }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const unmatched = article.pressRelease === null;

  useEffect(() => {
    if (unmatched) return;          // 매칭된 보도자료가 없으면 요청 자체를 보내지 않습니다.
    let alive = true;
    setDetail(null);
    setError(null);
    fetch(`${BASE_PATH}/data/details/${date}/${article.id}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: Detail) => alive && setDetail(d))
      .catch((e: Error) => alive && setError(e.message));
    return () => { alive = false; };
  }, [article.id, date, unmatched]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-8"
         onClick={onClose} role="dialog" aria-modal="true" aria-label="기사와 보도자료 대조">
      <div className="w-full max-w-4xl rounded-lg bg-surface ring-1 ring-hairline"
           onClick={(e) => e.stopPropagation()}>
        <header className="flex items-start gap-3 border-b p-4" style={{ borderColor: "var(--gridline)" }}>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-[12px] text-muted">
              <span>{article.outlet}</span>
              <CategoryBadge category={article.category} />
            </div>
            <h2 className="mt-1 text-[15px] font-semibold leading-snug">{article.title}</h2>
            <a href={article.url} target="_blank" rel="noopener noreferrer"
               className="mt-1 inline-block text-[12px] text-muted underline underline-offset-2">
              원문 보기 ↗
            </a>
          </div>
          <button onClick={onClose} aria-label="닫기"
                  className="rounded px-2 py-1 text-[13px] text-ink-2 hover:bg-plane">✕</button>
        </header>

        <div className="p-4">
          {unmatched ? (
            <div className="py-6">
              <p className="text-[13px] leading-relaxed text-ink-2">
                이 기사와 유사한 보도자료를 찾지 못했습니다. 대조할 원본이 없다는 뜻이며,
                복제율은 0%로 집계됩니다.
              </p>
              {article.rationale && (
                <p className="mt-4 rounded px-3 py-2 text-[13px] leading-relaxed text-ink-2"
                   style={{ background: "var(--plane)" }}>
                  <span className="font-medium text-ink">분류 근거</span> · {article.rationale}
                </p>
              )}
              {article.flaggedIssues.length > 0 && (
                <ul className="mt-3 list-inside list-disc space-y-1 text-[13px] text-ink-2">
                  {article.flaggedIssues.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              )}
            </div>
          ) : (
            <>
              {error && <p className="text-[13px] text-ink-2">상세 정보를 불러오지 못했습니다 ({error}).</p>}
              {!detail && !error && <p className="text-[13px] text-muted">불러오는 중…</p>}
            </>
          )}

          {detail && (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px]">
                <span className="text-ink-2">
                  매칭 보도자료:{" "}
                  <a href={detail.pressRelease.url} target="_blank" rel="noopener noreferrer"
                     className="underline underline-offset-2">{detail.pressRelease.title}</a>
                  <span className="text-muted"> · {detail.pressRelease.source}</span>
                </span>
                <span className="tabular">
                  문서 유사도 <b>{detail.docScore}%</b>
                </span>
                <span className="tabular">
                  그대로 옮긴 문장 <b style={{ color: "var(--dependent)" }}>{detail.copiedSentenceRatio}%</b>
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <section>
                  <h3 className="mb-2 text-[12px] font-medium text-ink-2">기사 문장</h3>
                  <ol className="space-y-1.5">
                    {detail.sentences.map((s) => (
                      <li key={s.i}
                          className="rounded px-2 py-1.5 text-[13px] leading-relaxed"
                          style={{
                            background: s.copied ? "color-mix(in srgb, var(--dependent) 14%, transparent)" : "transparent",
                            borderLeft: s.copied ? "2px solid var(--dependent)" : "2px solid transparent",
                          }}>
                        <span>{s.text}</span>
                        {s.sim > 0 && (
                          <span className="tabular ml-2 whitespace-nowrap text-[11px] text-muted">
                            일치 {(s.sim * 100).toFixed(0)}%
                          </span>
                        )}
                      </li>
                    ))}
                  </ol>
                </section>

                <section>
                  <h3 className="mb-2 text-[12px] font-medium text-ink-2">대응하는 보도자료 문장</h3>
                  <ol className="space-y-1.5">
                    {detail.sentences.map((s) => (
                      <li key={s.i}
                          className="rounded px-2 py-1.5 text-[13px] leading-relaxed"
                          style={{
                            background: s.copied ? "color-mix(in srgb, var(--dependent) 14%, transparent)" : "transparent",
                            borderLeft: s.copied ? "2px solid var(--dependent)" : "2px solid transparent",
                          }}>
                        {s.pr_text ?? <span className="text-muted">— 대응 문장 없음</span>}
                      </li>
                    ))}
                  </ol>
                </section>
              </div>

              {detail.excerptOnly && (
                <p className="mt-4 text-[11px] leading-relaxed text-muted">
                  저작권 보호를 위해 보도자료와 매칭된 문장만 표시합니다
                  {detail.omittedSentences > 0 && ` (비매칭 ${detail.omittedSentences}개 문장 생략)`}.
                  전문은 원문 링크에서 확인하세요.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

type Filter = "all" | "duplicated" | Category;

export function ArticleInspector({
  articles, threshold, date,
}: { articles: Article[]; threshold: number; date: string }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<Article | null>(null);

  const filtered = useMemo(() => {
    const rows = articles.filter((a) => {
      if (filter === "all") return true;
      if (filter === "duplicated") return a.isDuplicated;
      return a.category === filter;
    });
    return [...rows].sort((a, b) => b.duplication - a.duplication);
  }, [articles, filter]);

  const chips: { key: Filter; label: string; n: number }[] = [
    { key: "all", label: "전체", n: articles.length },
    { key: "duplicated", label: `복제 ${Math.round(threshold * 100)}%↑`, n: articles.filter((a) => a.isDuplicated).length },
    { key: "Watchdog", label: "감시", n: articles.filter((a) => a.category === "Watchdog").length },
    { key: "Cheerleader", label: "홍보", n: articles.filter((a) => a.category === "Cheerleader").length },
    { key: "Neutral", label: "중립", n: articles.filter((a) => a.category === "Neutral").length },
  ];

  return (
    <div>
      {/* 필터는 차트 위 한 줄에 */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {chips.map((c) => (
          <button key={c.key} onClick={() => setFilter(c.key)}
                  className={`rounded-full px-3 py-1 text-[12px] ring-1 transition-colors ${
                    filter === c.key
                      ? "bg-ink text-surface ring-transparent"
                      : "text-ink-2 ring-hairline hover:bg-plane"
                  }`}>
            {c.label} <span className="tabular opacity-70">{c.n}</span>
          </button>
        ))}
      </div>

      <div className="max-h-[520px] overflow-auto">
        <table className="w-full min-w-[680px] border-collapse text-[13px]">
          <thead>
            <tr className="border-b text-ink-2" style={{ borderColor: "var(--gridline)" }}>
              <th scope="col" className="sticky top-0 z-10 bg-surface px-3 py-2 text-left font-medium">기사</th>
              <th scope="col" className="sticky top-0 z-10 bg-surface px-3 py-2 text-left font-medium w-24">언론사</th>
              <th scope="col" className="sticky top-0 z-10 bg-surface px-3 py-2 text-left font-medium w-20">분류</th>
              <th scope="col" className="sticky top-0 z-10 bg-surface px-3 py-2 text-right font-medium w-28">복제율</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.id}
                  className="cursor-pointer border-b last:border-0 hover:bg-plane"
                  style={{ borderColor: "var(--gridline)" }}
                  onClick={() => setOpen(a)}>
                <td className="px-3 py-2.5">
                  <span className="line-clamp-1">{a.title}</span>
                  {a.syndicationSpread > 1 && (
                    <span className="ml-2 whitespace-nowrap text-[11px] text-muted">
                      {a.syndicationSpread}개 매체 동일 본문
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-ink-2">{a.outlet}</td>
                <td className="px-3 py-2.5"><CategoryBadge category={a.category} /></td>
                <td className="px-3 py-2.5 text-right">
                  <span className="inline-flex items-center justify-end gap-2">
                    <span className="relative block h-[8px] w-14 shrink-0 rounded-full"
                          style={{ background: "var(--track)" }}>
                      <span className="absolute left-0 top-0 h-full rounded-full"
                            style={{ width: `${a.duplication}%`, background: "var(--dependent)" }} />
                    </span>
                    <span className="tabular w-10 text-right">{a.duplication.toFixed(0)}%</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="py-8 text-center text-[13px] text-muted">해당 조건의 기사가 없습니다.</p>
        )}
      </div>

      {open && <DiffModal article={open} date={date} onClose={() => setOpen(null)} />}
    </div>
  );
}
