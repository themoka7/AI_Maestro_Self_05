"""한국어 텍스트 정규화 · 형태소 기반 유사도.

rapidfuzz.token_set_ratio 같은 어절 단위 비교는 한국어에서 조사/어미 때문에
"여수시는 / 여수시가 / 여수시의" 가 전부 다른 토큰이 되어 복제율을 과소평가합니다.
그래서 Kiwi 로 형태소를 뽑아 내용 형태소만 남긴 뒤 비교합니다.
"""
from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Iterable

from kiwipiepy import Kiwi

# 내용 형태소만 남깁니다. 조사(J*), 어미(E*), 기호(S*), 접사 일부는 버립니다.
CONTENT_TAGS = (
    "NNG", "NNP", "NNB", "NR", "NP",      # 체언
    "VV", "VA", "VX", "VCP", "VCN",        # 용언
    "MM", "MAG", "MAJ",                    # 수식언
    "XR", "XPN",                           # 어근/접두
    "SL", "SH", "SN",                      # 외국어/한자/숫자
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# 기사 말미 상용구: 기자명, 이메일, 저작권 고지, 무단전재 금지 등
_BOILERPLATE_RE = re.compile(
    r"(무단\s*전재|재배포\s*금지|저작권자?\s*ⓒ|Copyright\s*ⓒ|ⓒ\s*\w+|"
    r"[\w.+-]+@[\w-]+\.[\w.]+|<저작권자.*?>)",
    re.IGNORECASE,
)

_kiwi: Kiwi | None = None


def kiwi() -> Kiwi:
    """Kiwi 인스턴스는 로딩이 무거워 프로세스당 하나만 씁니다."""
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def clean_text(text: str | None) -> str:
    """HTML 태그/엔티티 제거, 상용구 제거, 공백 정규화."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _TAG_RE.sub(" ", t)
    t = html.unescape(t)
    t = _BOILERPLATE_RE.sub(" ", t)
    return _WS_RE.sub(" ", t).strip()


@lru_cache(maxsize=4096)
def morphs(text: str, max_tokens: int = 3000) -> tuple[str, ...]:
    """내용 형태소의 원형(lemma) 시퀀스. 조사/어미가 제거되어 활용형 차이에 둔감합니다."""
    text = clean_text(text)
    if not text:
        return ()
    out: list[str] = []
    for token in kiwi().tokenize(text):
        # 숫자/로마자는 1글자여도 유지, 그 외 내용 형태소는 2글자 이상만 (1글자 명사 노이즈 제거)
        keep = token.tag in ("SN", "SL") or (
            token.tag in CONTENT_TAGS and len(token.form) > 1
        )
        if keep:
            out.append(f"{token.form}/{token.tag[0]}")
            if len(out) >= max_tokens:
                break
    return tuple(out)


def ngrams(tokens: Iterable[str], n: int = 3) -> set[tuple[str, ...]]:
    seq = list(tokens)
    if len(seq) < n:
        return {tuple(seq)} if seq else set()
    return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def containment(a: set, b: set) -> float:
    """a 가 b 에 얼마나 포함되는가. 기사가 보도자료보다 짧게 잘려 실린 경우를 잡습니다."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def lcs_ratio(a: Iterable[str], b: Iterable[str]) -> float:
    """토큰 시퀀스의 최장 공통 부분수열 비율. 어순까지 그대로 베낀 경우를 잡습니다."""
    sa, sb = list(a), list(b)
    if not sa or not sb:
        return 0.0
    m = SequenceMatcher(None, sa, sb, autojunk=False)
    # quick_ratio 로 선체크: 상한이 낮으면 비싼 계산을 건너뜁니다.
    if m.quick_ratio() < 0.05:
        return 0.0
    return m.ratio()


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    return [s.text.strip() for s in kiwi().split_into_sents(text) if s.text.strip()]


def sentence_similarity(a: str, b: str) -> float:
    """문장 단위 유사도 (형태소 3-gram Jaccard 와 LCS 의 가중합)."""
    ta, tb = morphs(a), morphs(b)
    if not ta or not tb:
        return 0.0
    return 0.6 * jaccard(ngrams(ta), ngrams(tb)) + 0.4 * lcs_ratio(ta, tb)


def document_similarity(article: str, press_release: str) -> dict:
    """문서 단위 복제 지표.

    doc_score  : PRD 4.1 공식 (0.6*Jaccard_3gram + 0.4*LCS)
    containment: 기사 내용이 보도자료 안에 얼마나 들어있나 (기사가 짧게 잘렸을 때 유효)
    """
    ta, tb = morphs(article), morphs(press_release)
    if not ta or not tb:
        return {"doc_score": 0.0, "jaccard": 0.0, "lcs": 0.0, "containment": 0.0}
    ga, gb = ngrams(ta), ngrams(tb)
    j = jaccard(ga, gb)
    l = lcs_ratio(ta, tb)
    return {
        "doc_score": round(0.6 * j + 0.4 * l, 4),
        "jaccard": round(j, 4),
        "lcs": round(l, 4),
        "containment": round(containment(ga, gb), 4),
    }


def align_sentences(
    article: str,
    press_release: str,
    threshold: float = 0.85,
    min_chars: int = 15,
) -> dict:
    """기사 문장별로 가장 비슷한 보도자료 문장을 찾습니다.

    이게 있어야 UI 의 좌우 대조 하이라이트를 그릴 수 있습니다.
    문서 점수 하나만 계산하면 "어디를 베꼈는지"를 못 보여줍니다.
    """
    a_sents = split_sentences(article)
    p_sents = split_sentences(press_release)
    if not a_sents or not p_sents:
        return {"copied_sentence_ratio": 0.0, "sentence_map": []}

    # 비싼 비교 전에 형태소 집합을 미리 만들어 둡니다.
    p_grams = [ngrams(morphs(s)) for s in p_sents]

    smap: list[dict] = []
    copied = considered = 0
    for i, s in enumerate(a_sents):
        if len(s) < min_chars:          # 너무 짧은 문장은 판정에서 제외
            smap.append({"i": i, "text": s, "best_pr": None, "sim": 0.0, "copied": False})
            continue
        considered += 1
        sg = ngrams(morphs(s))
        best_j, best_idx = 0.0, -1
        for j_idx, pg in enumerate(p_grams):
            jv = jaccard(sg, pg)
            if jv > best_j:
                best_j, best_idx = jv, j_idx
        # 상위 후보에 대해서만 LCS 포함 정밀 점수를 계산합니다.
        sim = sentence_similarity(s, p_sents[best_idx]) if best_idx >= 0 and best_j > 0.15 else 0.0
        is_copied = sim >= threshold
        copied += int(is_copied)
        smap.append({
            "i": i,
            "text": s,
            "best_pr": best_idx if sim > 0 else None,
            "pr_text": p_sents[best_idx] if sim > 0 else None,
            "sim": round(sim, 4),
            "copied": is_copied,
        })

    ratio = copied / considered if considered else 0.0
    return {"copied_sentence_ratio": round(ratio, 4), "sentence_map": smap}
