export type Category = "Watchdog" | "Cheerleader" | "Neutral";

export interface Totals {
  articles: number;
  watchdog_rate: number;
  cheerleader_rate: number;
  neutral_rate: number;
  duplication_rate: number;
}

export interface Outlet {
  outlet: string;
  articles: number;
  watchdog: number;
  cheerleader: number;
  neutral: number;
  duplicated: number;
  watchdog_rate: number;
  cheerleader_rate: number;
  neutral_rate: number;
  duplication_rate: number;
  autonomy_score: number;
  sufficient_sample: boolean;
  rank: number | null;
}

export interface PressRelease {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string | null;
}

export interface Article {
  id: string;
  title: string;
  url: string;
  outlet: string;
  publishedAt: string;
  category: Category | null;
  score: number | null;
  confidence: number | null;
  rationale: string;
  flaggedIssues: string[];
  duplication: number;
  isDuplicated: boolean;
  docScore: number;
  copiedSentenceRatio: number;
  isCanonical: boolean;
  syndicationSpread: number;
  pressRelease: PressRelease | null;
}

export interface Summary {
  event: { id: string; name: string; description: string };
  date: string;
  generatedAt: string;
  totals: Totals;
  totalsUniqueOnly: Totals;
  params: {
    duplication_threshold: number;
    prior_weight: number;
    min_articles: number;
  };
  outlets: Outlet[];
  articles: Article[];
  coverage: Record<string, number>;
  goldenLabeled: number;
  excerptOnly: boolean;
}

export interface SentenceMatch {
  i: number;
  text: string;
  best_pr: number | null;
  pr_text: string | null;
  sim: number;
  copied: boolean;
}

export interface Detail {
  articleId: string;
  pressRelease: { title: string; url: string; source: string };
  docScore: number;
  copiedSentenceRatio: number;
  sentences: SentenceMatch[];
  excerptOnly: boolean;
}

export const CATEGORY_LABEL: Record<Category, string> = {
  Watchdog: "감시",
  Cheerleader: "홍보",
  Neutral: "중립",
};

/** 발산형 스케일: 감시(파랑) ← 중립(회색) → 의존(빨강) */
export const CATEGORY_VAR: Record<Category, string> = {
  Watchdog: "var(--watchdog)",
  Neutral: "var(--neutral-cat)",
  Cheerleader: "var(--dependent)",
};

/** 색만으로 구분하지 않기 위한 보조 기호 (범례·배지에 항상 동반) */
export const CATEGORY_MARK: Record<Category, string> = {
  Watchdog: "◆",
  Neutral: "■",
  Cheerleader: "▲",
};
