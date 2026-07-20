#!/usr/bin/env python3
"""
아파트 직접 추가: 사용자가 준 단지를 공식 데이터로 분석해 목록에 '직접 추가'로 넣는다.
사용:
  python3 add_apartment.py --name "단지명" --lawd 41131 --dong 단대동 [--naver 2660]
  (구 코드 lawd는 config 대상권역 참고. dong은 법정동명. naver=네이버 hscpNo(선택))
실거래·연식·면적(국토부) + 용적률·세대수·층수(건축물대장) + 강남구청역 직선거리 자동 계산.
"""
import os, sys, json, math, argparse, time
from collections import Counter, defaultdict
import collect_molit as M
import collect_bldg as B

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
MANUAL = os.path.join(BASE, "data", "manual.json")  # 직접 추가 전용(자동갱신에도 보존)
DC = json.load(open(os.path.join(BASE, "data", "dong_codes.json"), encoding="utf-8"))
ST = CFG["기준역"]

def load_manual():
    return json.load(open(MANUAL, encoding="utf-8")) if os.path.exists(MANUAL) else []
def save_manual(lst):
    json.dump(lst, open(MANUAL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def hav(a, b, c, d):
    R = 6371.0; p1, p2 = math.radians(a), math.radians(c)
    dp = math.radians(c - a); dl = math.radians(d - b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(x))

def norm(s):
    import re
    return re.sub(r"\(.*?\)", "", s or "").replace("아파트", "").replace(" ", "")

def ensure_region(lawd):
    """dong_codes 에 없는 구면 네이버에서 즉석 수집(28개 지역 밖 단지 추가용)."""
    if lawd in DC and DC[lawd].get("dongs"):
        return
    import urllib.request
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    req = urllib.request.Request(
        f"https://m.land.naver.com/map/getRegionList?cortarNo={lawd}00000",
        headers={"User-Agent": UA, "Referer": "https://m.land.naver.com/"})
    lst = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace"))
    lst = lst.get("result", {}).get("list", [])
    DC[lawd] = {
        "dongs": {x["CortarNm"]: x["CortarNo"] for x in lst},
        "coords": {x["CortarNm"]: [float(x.get("MapYCrdn", 0)), float(x.get("MapXCrdn", 0))] for x in lst},
    }
    B.DONGMAP[lawd] = DC[lawd]["dongs"]
    json.dump(DC, open(os.path.join(BASE, "data", "dong_codes.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"  · 지역 코드 즉석 수집: {lawd} ({len(lst)}개 동)")

def add(name, lawd, dong, naver=None):
    key = M.service_key()
    ensure_region(lawd)
    # 1) 실거래: 해당 구 최근 12개월에서 단지명·동 매칭
    deals = []
    for ymd in M.recent_months(12):
        items, err = M.parse(M.fetch(lawd, ymd, key))
        if err:
            continue
        for it in items:
            if norm(name) in norm(it["apt"]) and (dong in it["umd"] or it["umd"] in dong):
                deals.append(it)
        time.sleep(0.15)
    if not deals:
        print(f"❌ '{name}'({dong}) 실거래를 찾지 못했습니다. 이름/동/구코드를 확인하세요.")
        return None
    # 대표 평형: 20평(공급) 이상 중 거래 많은 것
    by_area = defaultdict(list)
    for d in deals:
        by_area[round(d["area"])].append(d)
    def supply(a): return round((a/3.3058)/0.75, 1)
    cand_areas = [a for a in by_area if supply(a) >= CFG["하드필터"]["공급면적_최소_평"]] or list(by_area)
    area = max(cand_areas, key=lambda a: len(by_area[a]))
    g = by_area[area]; g.sort(key=lambda x: x["date"], reverse=True)
    recent = g[0]; avg = round(sum(x["amount"] for x in g)/len(g))
    bb = Counter((d["bonbun"], d["bubun"]) for d in g).most_common(1)[0][0]
    build = max(x["build"] for x in g)

    entry = {
        "단지번호": f"직접-{lawd}-{dong}-{name}-{area}",
        "단지명": name, "주소": f"{dong}", "법정동명": dong, "법정동코드5": lawd,
        "지번본번": bb[0], "지번부번": bb[1],
        "매매최저가_만원": None, "매물개수": None,
        "실거래_직전_만원": recent["amount"], "실거래_평균_만원": avg,
        "실거래_거래일": recent["date"], "실거래_건수": len(g),
        "대중교통_분": None, "준공연도": build, "용적률": None,
        "대표평형_평": round(supply(area)), "대표평형_공급_m2": round(supply(area)*3.3058),
        "대표평형_전용_m2": area, "세대수": None, "층수": None,
        "노후도_코멘트": None, "실리뷰_코멘트": None, "감성점수": None,
        "네이버_hscpNo": naver, "추가유형": "직접",
    }
    # 2) 건축물대장: 용적률·건폐율·세대수·층수·용도·주차 (MOLIT umdCd를 bjdongCd로)
    bj = g[0].get("umdCd")
    if not bj:
        d10 = B.DONGMAP.get(lawd, {}).get(dong)
        bj = d10[5:] if d10 else None
    entry["법정동읍면동코드"] = g[0].get("umdCd")
    if bj:
        bun = str(bb[0]).zfill(4); ji = str(bb[1]).zfill(4)
        body = B.fetch(B.TITLE_EP, lawd, bj, bun, ji)
        if body:
            info, _ = B.parse(body)
            rbody = B.fetch(B.RECAP_EP, lawd, bj, bun, ji, tries=3)
            recap = B.parse_recap(rbody) if rbody else {}
            entry["용적률"] = recap.get("용적률") or info["용적률"]
            entry["건폐율"] = recap.get("건폐율") or info.get("건폐율")
            entry["세대수"] = recap.get("세대수") or info["세대수"]
            entry["층수"] = info.get("층수") or recap.get("층수")
            entry["용도"] = info.get("용도") or recap.get("용도")
            entry["주차대수"] = recap.get("주차대수") or info.get("주차대수")
            age = 2026 - build
            entry["노후도_코멘트"] = f"{build}년 준공(약 {age}년차) — " + \
                ("준신축·양호" if age <= 10 else "중간 연식" if age <= 20 else "노후 진행")
    # 3) 직선거리 + ODsay 실측 대중교통
    coords = DC.get(lawd, {}).get("coords", {})
    c = coords.get(dong) or next((v for k, v in coords.items() if dong.startswith(k) or k in dong), None)
    if c and c[0]:
        entry["직선거리_km"] = round(hav(ST["위도"], ST["경도"], c[0], c[1]), 1)
        try:
            import urllib.request, urllib.parse
            ok = os.environ.get("ODSAY_KEY") or CFG.get("대중교통", {}).get("odsay_key")
            if ok:
                url = (f"https://api.odsay.com/v1/api/searchPubTransPathT?SX={c[1]}&SY={c[0]}"
                       f"&EX={ST['경도']}&EY={ST['위도']}&apiKey={urllib.parse.quote(ok)}")
                rj = json.loads(urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "replace"))
                paths = rj.get("result", {}).get("path", [])
                if paths:
                    best = min(paths, key=lambda p: p["info"]["totalTime"])
                    entry["대중교통_분"] = best["info"]["totalTime"]
                    entry["대중교통_환승"] = max(0, best["info"].get("busTransitCount", 0)
                                          + best["info"].get("subwayTransitCount", 0) - 1)
        except Exception:
            pass

    # 4) manual.json 에 추가(같은 번호면 교체) — 자동 갱신에도 보존됨
    man = [x for x in load_manual() if x["단지번호"] != entry["단지번호"]]
    man.append(entry)
    save_manual(man)
    print(f"✅ 직접 추가: {name} · 실거래 {recent['amount']/10000:.2f}억 · {build}년 · "
          f"{entry['대표평형_평']}평 · 용적률 {entry['용적률']}% · 세대 {entry['세대수']} · "
          f"층수 {entry['층수']} · 직선 {entry.get('직선거리_km')}km")
    return entry

def remove(name):
    man = load_manual()
    kept = [x for x in man if name not in x["단지명"]]
    save_manual(kept)
    print(f"직접 추가 제거: '{name}' 포함 {len(man)-len(kept)}개 삭제 → 남은 {len(kept)}개")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--lawd")
    ap.add_argument("--dong")
    ap.add_argument("--naver", default=None)
    ap.add_argument("--remove", help="직접 추가 목록에서 이 이름 포함 항목 제거")
    a = ap.parse_args()
    if a.remove:
        remove(a.remove)
    else:
        if not (a.name and a.lawd and a.dong):
            ap.error("--name --lawd --dong 필요 (또는 --remove)")
        add(a.name, a.lawd, a.dong, a.naver)
