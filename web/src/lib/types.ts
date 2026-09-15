export type Category = "Watchdog" | "Cheerleader" | "Neutral";

/** 분류(Anthropic 키)가 없으면 프레이밍 관련 비율은 null 입니다. 복제율은 항상 있습니다. */
export interface Totals {
  articles: number;
  watchdog_rate: number | null;
  cheerleader_rate: number | null;
  neutral_rate: number | null;
  duplication_rate: number;
}

export interface Outlet {
  outlet: string;
  articles: number;
  /** 분류가 완료된 기사 수. 0 이면 프레이밍 지표가 전부 null 입니다. */
  classified: number;
  watchdog: number;
  cheerleader: number;
  neutral: number;
  duplicated: number;
  watchdog_rate: number | null;
  cheerleader_rate: number | null;
  neutral_rate: number | null;
  duplication_rate: number;
  autonomy_score: number | null;
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

export interface DailyPoint {
  date: string;
  articles: number;
  duplication_rate: number;
  watchdog_rate: number | null;
  autonomy_score: number | null;
}

/** 날짜를 가로지르는 언론사별 집계. 일별 비율의 평균이 아니라 원시 건수 합산 기준. */
export interface OutletCumulative extends Outlet {
  activeDays: number;
  /** 최근 7일 평균 자율성 − 그 이전 평균. 데이터가 부족하면 null. */
  trend: number | null;
  series: DailyPoint[];
}

export interface OutletAggregate {
  event: { id: string; name: string; description: string };
  window: { from: string; to: string; days: number };
  generatedAt: string;
  params: { duplication_threshold: number; prior_weight: number; min_articles: number };
  demo?: boolean;
  hasClassification: boolean;
  classifiedArticles: number;
  totals: Totals;
  daily: (Totals & { date: string })[];
  outlets: OutletCumulative[];
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
  hasClassification?: boolean;
  classifiedArticles?: number;
  goldenLabeled: number;
  excerptOnly: boolean;
  /** 합성 데모 데이터 여부 (분류가 전부 mock). 공개 화면에서 실측과 구분합니다. */
  demo?: boolean;
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
  /** excerpt 모드에서 저장하지 않은 비매칭 문장 수 */
  omittedSentences: number;
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
