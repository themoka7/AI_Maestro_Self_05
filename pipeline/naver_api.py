"""NAVER API HUB (네이버 클라우드 플랫폼) 검색 API 클라이언트.

2026년에 검색 API 가 개발자센터에서 NAVER API HUB 로 이관되었습니다.
바뀐 것:

    도메인   https://openapi.naver.com      →  https://naverapihub.apigw.ntruss.com
    경로     /v1/search/news.json           →  /search/v1/news        (버전 위치가 뒤바뀜)
    인증     X-Naver-Client-Id / -Secret    →  X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY
    과금     개발자센터 무료 일 25,000건     →  NCP 종량 과금

이관 과정에서 쇼핑·책·전문자료 검색은 종료되었고 뉴스 검색은 유지됩니다.

엔드포인트와 페이징 한도는 config/event.yaml 의 `api:` 섹션에서 덮어쓸 수 있습니다.
문서와 실제 동작이 다를 때 코드를 고치지 않고 설정만 바꿔 대응하기 위한 것입니다.
"""
from __future__ import annotations

import os
import time
from typing import Any, Iterator

import requests

DEFAULT_BASE_URL = "https://naverapihub.apigw.ntruss.com"
DEFAULT_NEWS_PATH = "/search/v1/news"
DEFAULT_MAX_START = 1000   # 구 API 기준. 실제 한도가 낮으면 아래에서 자동으로 멈춥니다.
DEFAULT_DISPLAY = 100

CREDENTIAL_HELP = """
NAVER API HUB 자격증명을 확인하세요.

  콘솔   https://console.ncloud.com  →  Services  →  NAVER API HUB
  인증키 마이페이지 → 인증키 관리 (X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY)

  1) API HUB 에서 '검색(Search)' API 를 신청·승인받았는지
  2) .env 의 NCP_API_KEY_ID / NCP_API_KEY 에 공백·따옴표가 섞이지 않았는지
  3) 구 개발자센터(X-Naver-Client-Id) 키는 더 이상 쓰이지 않습니다

  ※ 검색 API 는 2026년 개발자센터에서 NAVER API HUB 로 이관되었고, NCP 종량 과금입니다.
"""


class NaverAuthError(RuntimeError):
    """자격증명·권한 문제. 재시도해도 소용없으므로 별도 예외로 구분합니다."""


class NaverApiError(RuntimeError):
    pass


def _decode_error(resp: requests.Response) -> str:
    """APIGW 와 검색 API 는 에러 형식이 다릅니다. 둘 다 받아서 사람이 읽을 문자열로."""
    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return f"HTTP {resp.status_code}: {resp.text[:300]}"

    # APIGW 형식: {"error": {"errorCode": "200", "message": "...", "details": "..."}}
    if isinstance(body.get("error"), dict):
        e = body["error"]
        return (f"HTTP {resp.status_code} [{e.get('errorCode', '?')}] "
                f"{e.get('message', '')} {e.get('details', '')}".strip())
    # 검색 API 형식: {"errorCode": "024", "errorMessage": "..."}
    if "errorCode" in body:
        return (f"HTTP {resp.status_code} [{body.get('errorCode')}] "
                f"{body.get('errorMessage', '')}".strip())
    return f"HTTP {resp.status_code}: {str(body)[:300]}"


class NaverSearchClient:
    def __init__(self, api_cfg: dict | None = None) -> None:
        cfg = api_cfg or {}
        self.base_url = cfg.get("base_url", DEFAULT_BASE_URL).rstrip("/")
        self.news_path = cfg.get("news_path", DEFAULT_NEWS_PATH)
        self.max_start = int(cfg.get("max_start", DEFAULT_MAX_START))
        self.display = int(cfg.get("display", DEFAULT_DISPLAY))
        self.delay = float(cfg.get("request_delay", 0.1))

        key_id, key = credentials()
        self.session = requests.Session()
        self.session.headers.update({
            "X-NCP-APIGW-API-KEY-ID": key_id,
            "X-NCP-APIGW-API-KEY": key,
            "Accept": "application/json",
        })

    @property
    def news_url(self) -> str:
        return f"{self.base_url}{self.news_path}"

    def _get(self, params: dict) -> requests.Response:
        return self.session.get(self.news_url, params=params, timeout=15)

    def verify(self) -> None:
        """1건짜리 요청으로 자격증명과 엔드포인트를 미리 확인합니다.

        쿼리 5개 x 10페이지를 돌다 마지막에 401 을 보는 것보다 첫 요청에서
        원인을 지목해 주는 편이 낫습니다.
        """
        try:
            resp = self._get({"query": "테스트", "display": 1})
        except requests.RequestException as e:
            raise NaverApiError(f"{self.news_url} 에 연결하지 못했습니다: {e}") from e

        if resp.status_code in (401, 403):
            raise NaverAuthError(_decode_error(resp) + "\n" + CREDENTIAL_HELP)
        if resp.status_code == 404:
            raise NaverApiError(
                f"{self.news_url} → 404. 엔드포인트 경로가 바뀌었을 수 있습니다.\n"
                f"config/event.yaml 의 api.base_url / api.news_path 를 확인하세요."
            )
        if resp.status_code >= 400:
            raise NaverApiError(_decode_error(resp))

    def search_news(self, query: str, start: int, display: int | None = None) -> dict:
        params = {
            "query": query,
            "display": display or self.display,
            "start": start,
            "sort": "date",
        }
        resp = self._get(params)

        if resp.status_code == 429:
            raise NaverApiError("호출 한도 초과 (NCP API HUB 쿼터/스로틀링). 잠시 후 재시도하세요.")
        if resp.status_code in (401, 403):
            raise NaverAuthError(_decode_error(resp) + "\n" + CREDENTIAL_HELP)
        if resp.status_code >= 400:
            raise NaverApiError(_decode_error(resp))
        return resp.json()

    def paginate_news(self, query: str) -> Iterator[list[dict]]:
        """최신순으로 페이지를 순회합니다. 호출자가 원하는 지점에서 끊습니다.

        start 상한은 이관 후 낮아졌을 수 있어 문서값을 그대로 믿지 않습니다.
        상한을 넘어 400 이 나면 예외를 던지지 않고 조용히 멈춥니다.
        """
        start = 1
        while start <= self.max_start:
            try:
                data = self.search_news(query, start)
            except NaverApiError:
                if start == 1:
                    raise              # 첫 페이지 실패는 진짜 오류
                break                  # 페이징 한도에 걸린 것으로 보고 중단
            items = data.get("items", [])
            if not items:
                break
            yield items
            if len(items) < self.display:
                break
            start += self.display
            time.sleep(self.delay)


def credentials() -> tuple[str, str]:
    """NCP 인증키를 환경변수에서 읽습니다.

    구 개발자센터 변수명(NAVER_CLIENT_ID/SECRET)도 받아주되, 값이 그쪽에만 있으면
    이관 전 키일 가능성이 높으므로 경고 없이 넘기지 않습니다.
    """
    key_id = os.environ.get("NCP_API_KEY_ID") or os.environ.get("NAVER_CLIENT_ID")
    key = os.environ.get("NCP_API_KEY") or os.environ.get("NAVER_CLIENT_SECRET")
    if not key_id or not key:
        raise NaverAuthError(
            "NCP_API_KEY_ID / NCP_API_KEY 가 설정되지 않았습니다.\n" + CREDENTIAL_HELP
        )
    return key_id, key
