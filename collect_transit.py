#!/usr/bin/env python3
"""
ODsay 대중교통 길찾기로 각 동 → 강남구청역 실제 소요시간/환승 계산.
- 동 단위(중심좌표)로 계산·캐시(무료 한도 절약, 동 내 단지는 비슷).
- 대중교통_분 > 60 인 곳은 제외(진짜 통근권 필터).
- 실측이라 대중교통_추정 플래그 제거.
gen 전, filter_distance 뒤에 실행.
"""
import os, json, time, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
DBP = os.path.join(BASE, "data", "apartments.json")
DB = json.load(open(DBP, encoding="utf-8"))
DC = json.load(open(os.path.join(BASE, "data", "dong_codes.json"), encoding="utf-8"))

KEY = os.environ.get("ODSAY_KEY") or CFG.get("대중교통", {}).get("odsay_key", "")
ST = CFG["기준역"]
EX, EY = ST["경도"], ST["위도"]
MAXMIN = CFG["하드필터"]["강남구청역_대중교통_최대_분"]

CACHE_PATH = os.path.join(BASE, "data", "transit_cache.json")
CACHE = json.load(open(CACHE_PATH, encoding="utf-8")) if os.path.exists(CACHE_PATH) else {}

def find_coord(lawd, umd):
    dm = DC.get(lawd, {}).get("coords", {})
    if not umd: return None
    if umd in dm: return dm[umd]
    for p in umd.split():
        if p in dm: return dm[p]
    for k, v in dm.items():
        if umd.startswith(k) or k in umd: return v
    return None

def odsay(sx, sy):
    """(소요분, 환승수) 또는 (None, None)."""
    url = (f"https://api.odsay.com/v1/api/searchPubTransPathT?SX={sx}&SY={sy}"
           f"&EX={EX}&EY={EY}&apiKey={urllib.parse.quote(KEY)}")
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if "error" in d:
                return None, None  # 경로 없음/오류
            paths = d.get("result", {}).get("path", [])
            if not paths:
                return None, None
            best = min(paths, key=lambda p: p["info"]["totalTime"])
            i = best["info"]
            trans = max(0, i.get("busTransitCount", 0) + i.get("subwayTransitCount", 0) - 1)
            return i["totalTime"], trans
        except Exception:
            time.sleep(1)
    return None, None

# 후보에 등장하는 (lawd, 동) 목록 → 동별 1회만 계산
dongs = {}
for a in DB["단지목록"]:
    dongs.setdefault((a.get("법정동코드5"), a.get("법정동명")), None)

calc = 0
for (lawd, umd) in dongs:
    ck = f"{lawd}|{umd}"
    if ck in CACHE:
        dongs[(lawd, umd)] = CACHE[ck]; continue
    c = find_coord(lawd, umd)
    if not c or not c[0]:
        dongs[(lawd, umd)] = [None, None]; continue
    mins, tr = odsay(c[1], c[0])  # SX=경도, SY=위도
    CACHE[ck] = [mins, tr]; dongs[(lawd, umd)] = [mins, tr]
    calc += 1
    print(f"  {umd}: {mins}분" + (f" · 환승 {tr}" if mins else " (경로 없음)"))
    time.sleep(0.2)

json.dump(CACHE, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)

# 후보에 반영 + 60분 초과 제외
kept, dropped = [], []
for a in DB["단지목록"]:
    mins, tr = dongs.get((a.get("법정동코드5"), a.get("법정동명")), [None, None])
    if mins is not None:
        a["대중교통_분"] = mins; a["대중교통_환승"] = tr
        a.pop("대중교통_추정", None)
    if mins is not None and mins > MAXMIN:
        dropped.append((a, mins))
    else:
        kept.append(a)

DB["단지목록"] = kept
json.dump(DB, open(DBP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nODsay 계산 {calc}개 동 · 캐시 {len(CACHE)}건")
print(f"실측 {MAXMIN}분 초과 제외 {len(dropped)}개 · 남은 {len(kept)}개")
for a, m in sorted(dropped, key=lambda x: -x[1])[:8]:
    print(f"  - {a['단지명']} ({a['주소']}) {m}분")
