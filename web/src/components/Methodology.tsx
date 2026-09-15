import type { Summary } from "@/lib/types";
import { Card } from "./StatTile";

/**
 * 방법론 고지는 장식이 아닙니다.
 * 언론사를 실명으로 줄 세우는 화면이므로, 수치가 어떻게 나왔고 무엇을 못 재는지를
 * 같은 화면에서 밝히지 않으면 숫자가 혼자 돌아다니게 됩니다.
 */
export function Methodology({ summary }: { summary: Summary }) {
  const { params, coverage, goldenLabeled, totals } = summary;
  const collected = Object.values(coverage).reduce((a, b) => a + b, 0);
  const ok = coverage.ok ?? 0;
  const coverageRate = collected ? (ok / collected) * 100 : 0;

  return (
    <Card className="p-5">
      <h2 className="text-[14px] font-semibold">방법론과 한계</h2>

      {goldenLabeled === 0 && (
        <p className="mt-3 rounded px-3 py-2 text-[12px] leading-relaxed"
           style={{ background: "color-mix(in srgb, var(--dependent) 12%, transparent)" }}>
          <b>검증 라벨 0건.</b> 사람이 직접 라벨링한 검증 셋과 대조하기 전까지 이 화면의
          언론사별 수치는 내부 검토용입니다. <code>pipeline/evaluate.py</code> 로 표본을 뽑아
          라벨링한 뒤 Cohen&apos;s κ 를 확인하세요.
        </p>
      )}

      <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2.5 text-[12px] leading-relaxed sm:grid-cols-2">
        <div>
          <dt className="font-medium">복제 판정 기준</dt>
          <dd className="text-ink-2">
            형태소 3-gram Jaccard와 최장공통부분수열의 가중합이 {Math.round(params.duplication_threshold * 100)}%
            이상이거나, 보도자료와 {Math.round(params.duplication_threshold * 100)}% 이상 일치하는 문장이
            그만큼의 비율을 차지할 때. 조사·어미는 제거하고 비교합니다.
          </dd>
        </div>
        <div>
          <dt className="font-medium">자율성 점수</dt>
          <dd className="text-ink-2">
            0.6×감시비율 + 0.4×중립비율 − 0.5×복제비율 을 0~100으로 환산.
            각 비율은 전체 평균 쪽으로 당기는 보정(사전표본 {params.prior_weight})을 거쳐,
            기사 몇 건뿐인 매체가 상위에 오르지 않게 했습니다.
            기사 {params.min_articles}건 미만은 순위에서 제외합니다.
          </dd>
        </div>
        <div>
          <dt className="font-medium">본문 수집률</dt>
          <dd className="text-ink-2">
            수집 {collected}건 중 본문 확보 {ok}건 ({coverageRate.toFixed(1)}%).
            나머지는 robots.txt 차단·추출 실패로 분석에서 빠졌으며, 이 누락은 매체별로
            균등하지 않을 수 있습니다.
          </dd>
        </div>
        <div>
          <dt className="font-medium">전재 처리</dt>
          <dd className="text-ink-2">
            언론사 점수는 그 매체가 실제로 내보낸 모든 기사 기준입니다(전재도 그 매체의 선택이므로).
            같은 본문이 여러 매체에 실린 경우는 별도로 묶어 표시하며,
            이날 고유 기사는 {summary.totalsUniqueOnly.articles}건 / 전체 {totals.articles}건이었습니다.
          </dd>
        </div>
      </dl>

      <p className="mt-4 border-t pt-3 text-[11px] leading-relaxed text-muted"
         style={{ borderColor: "var(--gridline)" }}>
        이 지표는 취재 행위의 형태를 재는 것이지 기사의 사실성·품질·정치적 정당성을 재지 않습니다.
        보도자료를 인용한 기사가 곧 잘못된 기사는 아니며, 단순 사실 고지는 의도적으로 중립으로 분류됩니다.
        분류는 언어모델이 수행하므로 오분류가 존재합니다. 개별 기사 판정은 원문과 대조해 확인하세요.
      </p>
    </Card>
  );
}
