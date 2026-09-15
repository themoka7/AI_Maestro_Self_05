/**
 * 합성 데모 데이터 경고.
 *
 * 이 화면은 공개 URL 로 서빙되고 언론사 이름 옆에 숫자를 붙입니다.
 * 데모 데이터일 때 그 사실을 화면 맨 위에서 말하지 않으면, 실측으로 읽힙니다.
 * 산출물의 demo 플래그(분류가 전부 mock)로 자동 판단하므로 사람이 지울 일이 없습니다.
 */
export function DemoBanner() {
  return (
    <div
      role="status"
      className="mb-6 flex items-start gap-3 rounded-lg px-4 py-3 ring-1"
      style={{
        background: "color-mix(in srgb, var(--dependent) 10%, transparent)",
        // 색만으로 경고를 전달하지 않도록 기호와 문구를 함께 둡니다.
        ["--tw-ring-color" as string]: "color-mix(in srgb, var(--dependent) 35%, transparent)",
      }}
    >
      <span aria-hidden className="mt-[2px] text-[13px] leading-none" style={{ color: "var(--dependent)" }}>
        ▲
      </span>
      <p className="text-[13px] leading-relaxed">
        <b>합성 데모 데이터입니다.</b> 실제 보도를 분석한 결과가 아닙니다.
        화면 구성을 확인하기 위한 가상 데이터이며, 등장하는 매체명(가온통신·하늘일보 등)은
        실존하지 않습니다. 실제 수집이 한 번이라도 돌면 이 배너는 자동으로 사라집니다.
      </p>
    </div>
  );
}
