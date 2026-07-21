#!/usr/bin/env python3
"""
apartments.json + config.json → dashboard.html 생성.
- 선호 점수는 값이 있는 항목만으로 계산하고 가중치를 재정규화(null 항목은 제외).
- 템플릿(dashboard.tmpl.html)의 /*__PAYLOAD__*/ 자리에 데이터를 주입.
"""
import os, json, math, datetime, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
DB = json.load(open(os.path.join(BASE, "data", "apartments.json"), encoding="utf-8"))
W = CFG["가중치"]
NOW = datetime.date.today().year

def clamp(v, a, b): return max(a, min(b, v))

# 직접 추가(manual.json) 병합 — 자동 갱신에도 보존
_mp = os.path.join(BASE, "data", "manual.json")
_manual = json.load(open(_mp, encoding="utf-8")) if os.path.exists(_mp) else []
apts = DB["단지목록"] + _manual

# 같은 단지(법정동+단지명) 평형별 행 → 하나로 묶기(평형·가격 범위)
from collections import defaultdict
def merge_complexes(items):
    groups = defaultdict(list)
    for a in items:
        groups[(a.get("법정동코드5"), a.get("법정동명"), a.get("단지명"), a.get("추가유형", "조사"))].append(a)
    out = []
    for g in groups.values():
        g.sort(key=lambda x: x.get("대표평형_전용_m2", 0))
        b = dict(g[0])  # 단지 공통정보는 대표(가장 작은 평형)에서
        pys = [x["대표평형_평"] for x in g]
        exs = [x["대표평형_전용_m2"] for x in g]
        rec = [x["실거래_직전_만원"] for x in g if x.get("실거래_직전_만원") is not None]
        b["평형수"] = len(g)
        b["평_최소"], b["평_최대"] = min(pys), max(pys)
        b["전용_최소"], b["전용_최대"] = min(exs), max(exs)
        b["실거래_최저_만원"] = min(rec) if rec else None
        b["실거래_최고_만원"] = max(rec) if rec else None
        b["실거래_직전_만원"] = min(rec) if rec else b.get("실거래_직전_만원")  # 진입가=최저
        b["실거래_평균_만원"] = round(sum(x.get("실거래_평균_만원", 0) or 0 for x in g) / len(g)) if rec else None
        b["실거래_건수"] = sum((x.get("실거래_건수") or 0) for x in g)
        b["대표평형_평"] = max(pys)
        b["준공연도"] = max(x.get("준공연도", 0) for x in g)
        for f in ("세대수", "용적률", "건폐율", "층수", "주차대수"):
            vals = [x.get(f) for x in g if x.get(f) is not None]
            b[f] = max(vals) if vals else None
        b["용도"] = next((x.get("용도") for x in g if x.get("용도")), b.get("용도"))
        out.append(b)
    return out
apts = merge_complexes(apts)

# 제외지역: 주소에 특정 문자열(예: "화도읍")이 포함되면 제외. config에서 조정, 자동 갱신에도 유지.
_excl = CFG.get("하드필터", {}).get("제외지역_주소포함") or []
if _excl:
    _b = len(apts)
    apts = [a for a in apts if not any(x in (a.get("주소") or "") for x in _excl)]
    print(f"제외지역({', '.join(_excl)}) 제외: {_b - len(apts)}개 → 남은 {len(apts)}개")

# 네이버 매매 매물이 확인된 곳(>0)만 유지. 0건·미확인(네이버에서 안 잡힘=매물없음 추정) 제외.
# 직접 추가(manual)는 항상 유지. 매물 복귀 시 다음 갱신에 자동 재등장(영구삭제 아님).
_before = len(apts)
apts = [a for a in apts if a.get("추가유형") == "직접" or (a.get("네이버_매물수") or 0) > 0]
print(f"매물 없음/미확인 제외: {_before - len(apts)}개 → 남은 {len(apts)}개")

prices = [a["실거래_직전_만원"] for a in apts if a.get("실거래_직전_만원") is not None]
pmin, pmax = (min(prices), max(prices)) if prices else (0, 1)

def metrics(a):
    m = {}
    # 저평가도: 매물호가 있으면 실거래 대비, 없으면 실거래 저렴도(세트 내 상대)
    if a.get("매매최저가_만원") is not None and a.get("실거래_평균_만원"):
        u = clamp((a["실거래_평균_만원"] - a["매매최저가_만원"]) / a["실거래_평균_만원"], -0.15, 0.30)
        m["저평가도"] = (u + 0.15) / 0.45
    elif a.get("실거래_직전_만원") is not None:
        cap = CFG["하드필터"]["매매최저가_최대_만원"]  # 5억 고정 기준(이상치에 안 흔들림)
        m["저평가도"] = clamp((cap - a["실거래_직전_만원"]) / (cap - 10000), 0, 1)  # 쌀수록 ↑
    if a.get("대중교통_분") is not None:
        mm = CFG["하드필터"]["강남구청역_대중교통_최대_분"]  # 통근 상한(현 70분)
        m["대중교통시간"] = clamp((mm - a["대중교통_분"]) / (mm - 10), 0, 1)
    elif a.get("직선거리_km") is not None:
        m["대중교통시간"] = clamp((26 - a["직선거리_km"]) / (26 - 3), 0, 1)
    if a.get("준공연도"):
        m["연식"] = clamp((a["준공연도"] - 1996) / (NOW - 1996), 0, 1)
    if a.get("용적률") is not None:
        m["용적률"] = clamp((250 - a["용적률"]) / (250 - 120), 0, 1)
    if a.get("대표평형_평"):
        m["평수"] = clamp((a["대표평형_평"] - 20) / (45 - 20), 0, 1)
    if a.get("세대수") is not None:
        m["세대수"] = clamp((math.log(a["세대수"]) - math.log(50)) / (math.log(3000) - math.log(50)), 0, 1)
    if a.get("감성점수") is not None:
        m["리뷰_노후도"] = clamp(a["감성점수"], 0, 1)
    return m

def score(a):
    m = metrics(a)
    wsum = sum(W[k] for k in m)
    if not wsum:
        return 0
    return round(sum(W[k] * v for k, v in m.items()) / wsum * 100)

def region_group(addr):
    """주소를 시(市) 단위 권역으로. 서울은 '서울'로 묶고, 경기는 시 이름으로."""
    p = (addr or "").strip().split()
    if not p: return "기타"
    if p[0] == "서울": return "서울"
    if p[0] == "경기": return p[1] if len(p) > 1 else "경기"
    t = p[0]                       # 예: '남양주시', '용인', '안양', '군포시'
    return t if t.endswith("시") else t + "시"

def est_rooms(m2):  # 전용면적 기반 방 개수 추정(아파트 통상 기준)
    if not m2: return None
    return 2 if m2 < 60 else 3 if m2 < 95 else 4

# 수동 오버레이: 자동수집 단지에 메모·링크 등을 덧입힌다(자동 갱신에도 유지).
# data/overrides.json = [{ "단지명": ..., "법정동명": (선택), "set": { "가격메모": ..., "분양홈페이지": ... } }, ...]
_ovp = os.path.join(BASE, "data", "overrides.json")
_overrides = json.load(open(_ovp, encoding="utf-8")) if os.path.exists(_ovp) else []
def apply_overrides(a):
    for ov in _overrides:
        if ov.get("단지명") and ov["단지명"] != a.get("단지명"): continue
        if ov.get("법정동명") and ov["법정동명"] not in (a.get("법정동명") or ""): continue
        for k, v in (ov.get("set") or {}).items():
            a[k] = v

for a in apts:
    a.setdefault("추가유형", "조사")
    apply_overrides(a)
    a["권역"] = region_group(a.get("주소", ""))
    a["방수_최소"] = est_rooms(a.get("전용_최소", a.get("대표평형_전용_m2", 0)))
    a["방수_최대"] = est_rooms(a.get("전용_최대", a.get("대표평형_전용_m2", 0)))
    if a.get("주차대수") and a.get("세대수"):
        a["세대당주차"] = round(a["주차대수"] / a["세대수"], 2)
    a["_score"] = score(a)
    # 현재 매물 호가 확인용 링크
    if a.get("네이버_hscpNo"):
        a["매물링크_네이버"] = f"https://fin.land.naver.com/complexes/{a['네이버_hscpNo']}"
    else:
        a["매물링크_네이버"] = "https://m.land.naver.com/search/result/" + urllib.parse.quote(a["단지명"])
    a["매물링크_호갱"] = a.get("호갱링크") or ("https://www.google.com/search?q=" +
        urllib.parse.quote(f"{a['단지명']} {a.get('법정동명','')} 호갱노노"))

regions = " · ".join(r["이름"] for r in CFG["대상권역"]["목록"] if r.get("status") == "active")
payload = {
    "meta": {
        "generated": DB.get("생성일시", ""),
        "top_n": CFG["추천"]["top_n"],
        "regions": regions,
        "station": CFG["기준역"]["이름"],
        "sample": DB.get("샘플여부", False),
    },
    "filters": CFG["하드필터"],
    "data": apts,
}

tmpl = open(os.path.join(BASE, "dashboard.tmpl.html"), encoding="utf-8").read()
html = tmpl.replace("/*__PAYLOAD__*/{}", json.dumps(payload, ensure_ascii=False))
out = os.path.join(BASE, "dashboard.html")
open(out, "w", encoding="utf-8").write(html)
print(f"✅ 대시보드 생성 → {out}  (단지 {len(apts)}개)")
print("상위 5:", [(a['단지명'], a['_score']) for a in sorted(apts, key=lambda x: -x['_score'])[:5]])
