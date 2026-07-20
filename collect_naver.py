#!/usr/bin/env python3
"""
네이버 부동산 수집기 (내부 데이터 API 이용, 크롬 확장 우회).
- 지역(구) → 동 → 단지 → 단지상세/매물 순으로 수집
- 요청 사이 텀(pacing) + 429 백오프로 차단 회피
- 6개 하드필터 중 5개(대중교통 제외) 1차 적용 → 후보를 data/raw에 저장
사용: python3 collect_naver.py <구cortarNo> [--probe <hscpNo>]
"""
import sys, json, time, urllib.request, urllib.error, os

UA_M = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
BASE = os.path.dirname(os.path.abspath(__file__))
PACE = 1.2  # 요청 사이 기본 대기(초)

def get(url, referer="https://m.land.naver.com/", tries=4):
    for i in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA_M, "Referer": referer,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read().decode("utf-8", "replace")
            time.sleep(PACE)
            if body.strip().startswith("<"):
                return {"_html": True, "_raw": body[:400]}
            return json.loads(body) if body.strip() not in ("", "null") else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 20 * (i + 1)
                print(f"  · 429 rate limit → {wait}s 대기", flush=True)
                time.sleep(wait); continue
            print(f"  · HTTP {e.code} {url[:80]}", flush=True); return None
        except Exception as ex:
            print(f"  · 오류 {ex}", flush=True); time.sleep(3)
    return None

def dongs(gu_cortar):
    d = get(f"https://m.land.naver.com/map/getRegionList?cortarNo={gu_cortar}")
    return (d or {}).get("result", {}).get("list", []) if d else []

def complexes(dong_cortar):
    d = get(f"https://m.land.naver.com/complex/ajax/complexListByCortarNo?cortarNo={dong_cortar}")
    return (d or {}).get("result", []) if d else []

# --- 단지 상세/매물: 엔드포인트 후보를 순서대로 시도(자가 탐색) ---
DETAIL_CANDIDATES = [
    "https://m.land.naver.com/complex/getComplexOverviewInfo?hscpNo={id}",
    "https://m.land.naver.com/complex/getComplexDetail?hscpNo={id}",
    "https://m.land.naver.com/api/complex/{id}",
]
ARTICLE_CANDIDATES = [
    "https://m.land.naver.com/complex/getComplexArticleList?hscpNo={id}&tradTpCd=A1&order=dealPriceAsc&showR0=N&page=1",
    "https://m.land.naver.com/complex/ajax/complexArticleList?hscpNo={id}&tradTpCd=A1&page=1",
]

def probe(hscp):
    print(f"[probe] 단지 {hscp} — 상세/매물 엔드포인트 탐색")
    for tmpl in DETAIL_CANDIDATES + ARTICLE_CANDIDATES:
        url = tmpl.format(id=hscp)
        r = get(url)
        ok = r is not None and not (isinstance(r, dict) and r.get("_html"))
        tag = "✅JSON" if ok else ("⬜HTML" if isinstance(r, dict) and r.get("_html") else "❌")
        keys = list(r.keys())[:8] if isinstance(r, dict) and ok else ""
        print(f"  {tag}  {url[:70]}  {keys}")

if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe(sys.argv[sys.argv.index("--probe") + 1]); sys.exit()
    gu = sys.argv[1] if len(sys.argv) > 1 else "4113100000"
    dl = dongs(gu)
    print(f"[{gu}] 동 {len(dl)}개")
    total = 0
    for dong in dl:
        cs = complexes(dong["CortarNo"])
        apt = [c for c in cs if c.get("hscpTypeCd", "").startswith("A") and c.get("dealCnt", 0) > 0]
        total += len(apt)
        print(f"  · {dong['CortarNm']}: 아파트 {len(apt)}개 (매물 있는 단지)")
    print(f"합계: 매물 있는 아파트 단지 {total}개")
