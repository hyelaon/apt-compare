#!/usr/bin/env python3
"""
각 후보 단지의 네이버 단지ID(hscpNo)를 찾아 실제 매물 페이지 링크를 넣는다.
- 네이버 모바일 지역 단지목록 API(complexListByCortarNo)로 동별 단지 조회 → 이름 매칭
- 링크: https://fin.land.naver.com/complexes/{hscpNo}  (네이버페이 부동산, 매물 표시)
gen 전에 실행.
"""
import os, json, time, re, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
DBP = os.path.join(BASE, "data", "apartments.json")
DB = json.load(open(DBP, encoding="utf-8"))
DC = json.load(open(os.path.join(BASE, "data", "dong_codes.json"), encoding="utf-8"))
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"

def norm(s):
    s = re.sub(r"\(.*?\)", "", s or "")            # 괄호 제거
    s = s.replace("아파트", "").replace(" ", "")
    return s

def dong_code(lawd, umd):
    dm = DC.get(lawd, {}).get("dongs", {})
    if umd in dm: return dm[umd]
    for p in (umd or "").split():
        if p in dm: return dm[p]
    for k, v in dm.items():
        if umd and (umd.startswith(k) or k in umd): return v
    return None

_complex_cache = {}  # dongCortar -> [ {hscpNo,hscpNm} ]
def complexes(dongCortar):
    if dongCortar in _complex_cache:
        return _complex_cache[dongCortar]
    try:
        req = urllib.request.Request(
            f"https://m.land.naver.com/complex/ajax/complexListByCortarNo?cortarNo={dongCortar}",
            headers={"User-Agent": UA, "Referer": "https://m.land.naver.com/"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", "replace")).get("result", [])
        time.sleep(0.25)
    except Exception:
        data = []
    _complex_cache[dongCortar] = data
    return data

hit = miss = 0
for a in DB["단지목록"]:
    dc = dong_code(a.get("법정동코드5"), a.get("법정동명"))
    hscp = None; deal = None
    if dc:
        cn = norm(a["단지명"])
        best = None
        for c in complexes(dc):
            nm = norm(c.get("hscpNm", ""))
            if not nm: continue
            if nm == cn or cn in nm or nm in cn:
                best = c
                if nm == cn: break
        if best:
            hscp = best["hscpNo"]
            deal = best.get("dealCnt")  # 현재 매매 매물 수
    a["네이버_hscpNo"] = hscp
    a["네이버_매물수"] = deal
    if hscp: hit += 1
    else: miss += 1

json.dump(DB, open(DBP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"네이버 단지ID 매칭: 성공 {hit} · 실패 {miss} / {len(DB['단지목록'])}")
