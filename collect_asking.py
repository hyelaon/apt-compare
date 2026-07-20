#!/usr/bin/env python3
"""
호가(현재 매매 매물) 범위를 fin.land(네이버페이 부동산) front-api로 수집 — 베스트에포트.
- 네이버가 차단(429)하면 조용히 건너뜀(다음 실행에서 재시도).
- 성공 시 단지별 매매 호가 최저~최고(만원)를 apartments.json 에 기록.
- 첫 성공 응답은 data/asking_debug.json 에 저장(구조 확인/파서 보정용).
사용: python3 collect_asking.py   (gen 전에 실행)
"""
import os, re, json, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
DBP = os.path.join(BASE, "data", "apartments.json")
DB = json.load(open(DBP, encoding="utf-8"))
CACHE_PATH = os.path.join(BASE, "data", "asking_cache.json")
CACHE = json.load(open(CACHE_PATH, encoding="utf-8")) if os.path.exists(CACHE_PATH) else {}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
DEBUG = os.path.join(BASE, "data", "asking_debug.json")

def price_to_man(s):
    s = str(s).replace(",", "").strip()
    if "억" in s:
        p = s.split("억"); man = 0
        a = re.sub("[^0-9]", "", p[0] or "0"); man += (int(a) if a else 0) * 10000
        rest = re.sub("[^0-9]", "", p[1]) if len(p) > 1 else ""
        if rest: man += int(rest)
        return man or None
    d = re.sub("[^0-9]", "", s)
    return int(d) if d else None

PRICE_KEYS = ("dealorwarrantprc", "price", "dealprice", "prc", "pricemax", "pricemin", "dealprc")
def collect_prices(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (str, int)) and any(p in k.lower() for p in PRICE_KEYS):
                m = price_to_man(v)
                if m and 3000 <= m <= 1000000:  # 3천만~100억 사이만
                    out.append(m)
            else:
                collect_prices(v, out)
    elif isinstance(obj, list):
        for x in obj: collect_prices(x, out)

def fetch(hscp):
    url = (f"https://fin.land.naver.com/front-api/v1/complex/article/list"
           f"?complexNumber={hscp}&tradeTypes=A1&page=1&size=50")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json", "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": f"https://fin.land.naver.com/complexes/{hscp}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def main():
    targets = [a for a in DB["단지목록"] if a.get("네이버_hscpNo")]
    # 차단 여부 먼저 확인(첫 대상 1건)
    if not targets:
        print("네이버 단지ID가 있는 대상이 없음"); return
    try:
        first = fetch(targets[0]["네이버_hscpNo"])
    except urllib.error.HTTPError as e:
        print(f"fin.land 접근 실패(HTTP {e.code}) — 네이버 차단 중, 다음 실행에서 재시도."); return
    except Exception as e:
        print(f"오류 {e} — 건너뜀."); return
    # 첫 성공 응답 저장(구조 확인용)
    open(DEBUG, "w", encoding="utf-8").write(first[:20000])
    print("✅ fin.land 접근 성공 — 호가 수집 시작 (debug 저장됨)")

    ok = 0
    for a in targets:
        hscp = a["네이버_hscpNo"]; ck = str(hscp)
        try:
            body = CACHE.get(ck, {}).get("_raw") or fetch(hscp)
        except Exception:
            time.sleep(1); continue
        prices = []
        try:
            collect_prices(json.loads(body), prices)
        except Exception:
            prices = []
        if prices:
            lo, hi = min(prices), max(prices)
            a["호가_최저_만원"] = lo; a["호가_최고_만원"] = hi; a["호가_매물수"] = len(prices)
            ok += 1
        time.sleep(0.5)

    json.dump(DB, open(DBP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"호가 채운 단지: {ok} / {len(targets)}")

if __name__ == "__main__":
    main()
