#!/usr/bin/env python3
"""
호갱노노 링크로 단지 직접 추가. 페이지 임베드 데이터에서 정보 추출 →
건축물대장 조회(등록됐으면 공식값) 또는 호갱노노 값으로 채워 manual.json 에 추가.
사용: python3 add_hogangnono.py <호갱노노_URL_또는_ID>
"""
import sys, os, re, json, math, urllib.request, urllib.parse
import collect_bldg as B

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
DC = json.load(open(os.path.join(BASE, "data", "dong_codes.json"), encoding="utf-8"))
MANUAL = os.path.join(BASE, "data", "manual.json")
ST = CFG["기준역"]; OKEY = CFG["대중교통"]["odsay_key"]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

def hav(a, b, c, d):
    R = 6371; p1, p2 = math.radians(a), math.radians(c)
    dp = math.radians(c-a); dl = math.radians(d-b)
    return 2*R*math.asin(math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))

def extract(url):
    h = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20).read().decode("utf-8", "replace")
    m = re.search(r'"region_code":"(\d+)","name":"([^"]+)","address":"([^"]+)","road_address":"([^"]*)"', h)
    if not m: return None
    rc, name, addr, road = m.groups()
    seg = h[m.start():m.start()+1500]
    def f(k, s=seg):
        mm = re.search(r'"%s":\s*"?([^",}]+)"?' % k, s); return mm.group(1) if mm else None
    return {"region_code": rc, "name": name, "address": addr, "road_address": road,
            "total_household": f("total_household"), "floor_max": f("floor_max"),
            "floor_area_ratio": f("floor_area_ratio"), "building_coverage_ratio": f("building_coverage_ratio"),
            "approval_date": f("approval_date"), "company": f("company"), "trade_count": f("trade_count")}

def odsay(c):
    if not c or not c[0]: return None, None, None
    km = round(hav(ST["위도"], ST["경도"], c[0], c[1]), 1)
    try:
        url = f"https://api.odsay.com/v1/api/searchPubTransPathT?SX={c[1]}&SY={c[0]}&EX={ST['경도']}&EY={ST['위도']}&apiKey={urllib.parse.quote(OKEY)}"
        paths = json.loads(urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "replace")).get("result", {}).get("path", [])
        if paths:
            best = min(paths, key=lambda p: p["info"]["totalTime"])
            return best["info"]["totalTime"], max(0, best["info"].get("busTransitCount", 0)+best["info"].get("subwayTransitCount", 0)-1), km
    except Exception: pass
    return None, None, km

def main(url):
    if not url.startswith("http"): url = "https://hogangnono.com/apt/" + url
    d = extract(url)
    if not d:
        print("❌ 페이지에서 단지 정보를 못 찾음"); return
    rc = d["region_code"]; lawd = rc[:5]; bjdong = rc[5:]
    am = re.search(r'([가-힣]+(?:동|읍|면|리|가\d?))\s', d["address"] + " ")
    dong = am.group(1) if am else d["address"].split()[-2]
    jib = re.search(r'(\d+)-?(\d+)?\s*$', d["address"])
    bun = (jib.group(1) if jib else "0").zfill(4); ji = (jib.group(2) or "0").zfill(4)
    # 좌표
    coords = DC.get(lawd, {}).get("coords", {})
    c = coords.get(dong) or next((v for k, v in coords.items() if dong.startswith(k) or k in dong), None)
    mins, trans, km = odsay(c)
    # 건축물대장 시도(등록됐으면 공식값 우선)
    vlrat = bcrat = hh = flr = park = purps = None
    body = B.fetch(B.TITLE_EP, lawd, bjdong, bun, ji)
    if body:
        info, _ = B.parse(body)
        rb = B.fetch(B.RECAP_EP, lawd, bjdong, bun, ji, tries=3)
        rec = B.parse_recap(rb) if rb else {}
        vlrat = rec.get("용적률") or info.get("용적률"); bcrat = rec.get("건폐율") or info.get("건폐율")
        hh = rec.get("세대수") or info.get("세대수"); flr = info.get("층수") or rec.get("층수")
        park = rec.get("주차대수") or info.get("주차대수"); purps = info.get("용도")
    # 호갱노노 값으로 폴백
    def i(x):
        try: return int(float(x))
        except: return None
    src = "건축물대장" if vlrat else "호갱노노"
    vlrat = vlrat or i(d["floor_area_ratio"]); bcrat = bcrat or i(d["building_coverage_ratio"])
    hh = hh or i(d["total_household"]); flr = flr or i(d["floor_max"])
    yr = i((d["approval_date"] or "")[:4]) or 2026
    has_deal = (i(d["trade_count"]) or 0) > 0
    entry = {
        "단지번호": f"직접-{lawd}-{dong}-{d['name']}", "단지명": d["name"],
        "주소": f"{d['address'].split()[0][:2]} {' '.join(d['address'].split()[1:3])}" if len(d['address'].split())>2 else d['address'],
        "법정동명": dong, "법정동코드5": lawd, "법정동읍면동코드": bjdong,
        "매매최저가_만원": None, "매물개수": None,
        "실거래_직전_만원": None, "실거래_평균_만원": None, "실거래_거래일": None, "실거래_건수": None,
        "준공연도": yr, "용적률": vlrat, "건폐율": bcrat, "세대수": hh, "층수": flr,
        "대표평형_평": None, "대표평형_전용_m2": None, "대표평형_공급_m2": None,
        "용도": purps or ("아파트(분양예정)" if not has_deal else "아파트"), "주차대수": park,
        "노후도_코멘트": f"{yr}년{'(입주예정)' if not has_deal else ''} · {hh or '?'}세대 {flr or '?'}층"
                    + (f" · 시공 {d['company']}" if d.get("company") else "") + (" (분양중)" if not has_deal else ""),
        "실리뷰_코멘트": None, "감성점수": None, "네이버_hscpNo": None, "네이버_매물수": None,
        "호갱링크": url, "대중교통_분": mins, "대중교통_환승": trans, "직선거리_km": km,
        "추가유형": "직접",
    }
    man = json.load(open(MANUAL, encoding="utf-8")) if os.path.exists(MANUAL) else []
    man = [x for x in man if x["단지번호"] != entry["단지번호"]]; man.append(entry)
    json.dump(man, open(MANUAL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 추가({src}): {d['name']} · {hh}세대 · 용적 {vlrat}%·건폐 {bcrat}% · {flr}층 · 강남구청역 {mins}분 · {yr}년")

if __name__ == "__main__":
    main(sys.argv[1])
