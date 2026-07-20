#!/usr/bin/env python3
"""
동 중심 좌표로 강남구청역까지 직선거리를 계산해:
- 직선거리_km 표시
- 대중교통_분(추정) = 직선거리 기반 근사치 (실측 불가 대체)
- 너무 먼 곳(추정 60분 초과) 제외
실측 대중교통 대신 쓰는 근사 보정. gen 전에 실행.
"""
import os, json, math

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
DBP = os.path.join(BASE, "data", "apartments.json")
DB = json.load(open(DBP, encoding="utf-8"))
DC = json.load(open(os.path.join(BASE, "data", "dong_codes.json"), encoding="utf-8"))

ST = CFG["기준역"]
SLAT, SLON = ST["위도"], ST["경도"]
# ODsay 실측 대중교통이 진짜 필터. 여기선 ODsay 호출 아낄 초광역 컷만(35km).
DIST_CUTOFF_KM = 35

def hav(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# 동 좌표 조회 (읍/면 단위 폴백 포함)
def find_coord(lawd, umd):
    dm = DC.get(lawd, {}).get("coords", {})
    if not umd: return None
    if umd in dm: return dm[umd]
    # "화도읍 묵현리" 처럼 읍/면+리 형태 → 읍/면 좌표로 폴백
    for p in umd.split():
        if p in dm: return dm[p]
    for k, v in dm.items():
        if umd.startswith(k) or k in umd: return v
    return None

kept, dropped = [], []
for a in DB["단지목록"]:
    c = find_coord(a.get("법정동코드5"), a.get("법정동명"))
    if not c or not c[0]:
        a["직선거리_km"] = None
        kept.append(a); continue   # 좌표 없으면 보존(판단 보류)
    km = round(hav(SLAT, SLON, c[0], c[1]), 1)
    a["직선거리_km"] = km
    if km > DIST_CUTOFF_KM:
        dropped.append((a, km))
    else:
        kept.append(a)

DB["단지목록"] = kept
json.dump(DB, open(DBP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"거리 보정(직선 {DIST_CUTOFF_KM}km 이내 유지): 유지 {len(kept)} · 제외 {len(dropped)}")
far = sorted(dropped, key=lambda x: -x[1])[:8]
for a, km in far:
    print(f"  - {a['단지명']} ({a['주소']}) 직선 {km}km")
