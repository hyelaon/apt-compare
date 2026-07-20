#!/usr/bin/env python3
"""
국토교통부 아파트 매매 실거래가 수집기 (공공데이터 공식 API).
- data.go.kr '아파트 매매 실거래가 상세 자료' API 사용 (합법·안정)
- 대상 구(법정동코드)별 최근 N개월 거래를 모아 단지×평형으로 집계
- 하드필터(건축년도≥1996, 실거래≤5억, 공급평≥20) 1차 적용
- 결과를 data/apartments.json 에 저장 (세대수·용적률·대중교통·리뷰는 이후 보강)

사용:
  MOLIT_KEY='발급받은Decoding키' python3 collect_molit.py
  또는 config.json 의 공공데이터.service_key 에 키를 넣고 실행
"""
import os, sys, json, time, datetime, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
ENDPOINT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/xml, text/xml, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.data.go.kr/",
}

def service_key():
    return os.environ.get("MOLIT_KEY") or CFG["공공데이터"].get("service_key", "")

def recent_months(n):
    d = datetime.date.today().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d.strftime("%Y%m"))
        d = (d - datetime.timedelta(days=1)).replace(day=1)
    return out

def fetch(lawd, ymd, key):
    # Decoding 키(특수문자 포함)를 안전하게 인코딩. 이미 %가 있으면 인코딩된 키로 간주.
    sk = key if "%" in key else urllib.parse.quote(key, safe="")
    url = (f"{ENDPOINT}?serviceKey={sk}&LAWD_CD={lawd}&DEAL_YMD={ymd}"
           f"&pageNo=1&numOfRows=1000")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")

def parse(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items, "XML 파싱 실패"
    # 에러 메시지 확인
    header = root.find(".//cmmMsgHeader")
    if header is not None:
        return items, header.findtext("returnAuthMsg") or header.findtext("errMsg") or "API 오류"
    result_code = root.findtext(".//resultCode")
    if result_code not in (None, "00", "000"):
        return items, root.findtext(".//resultMsg") or f"코드 {result_code}"
    for it in root.findall(".//item"):
        g = lambda t: (it.findtext(t) or "").strip()
        try:
            amt = int(g("dealAmount").replace(",", ""))
        except ValueError:
            continue
        items.append({
            "apt": g("aptNm"), "umd": g("umdNm"), "jibun": g("jibun"),
            "bonbun": g("bonbun"), "bubun": g("bubun"), "umdCd": g("umdCd"),
            "amount": amt,  # 만원
            "area": float(g("excluUseAr") or 0),  # 전용 ㎡
            "build": int(g("buildYear") or 0),
            "floor": g("floor"),
            "date": f"{g('dealYear')}-{int(g('dealMonth') or 0):02d}-{int(g('dealDay') or 0):02d}",
            "ymd": f"{g('dealYear')}{int(g('dealMonth') or 0):02d}",
        })
    return items, None

def pyeong_supply(area_m2):
    # 전용㎡ → 공급평 추정 (전용률 약 0.75 가정)
    return round((area_m2 / 3.3058) / 0.75, 1)

def main():
    key = service_key()
    if not key:
        print("❌ 인증키가 없습니다. MOLIT_KEY 환경변수 또는 config.json 공공데이터.service_key 에 넣어주세요.")
        sys.exit(1)
    regions = [r for r in CFG["대상권역"]["목록"] if r.get("status") == "active"]
    months = recent_months(CFG["공공데이터"].get("최근_개월수", 12))
    F = CFG["하드필터"]
    print(f"대상: {[r['이름'] for r in regions]} · 최근 {len(months)}개월")

    all_deals = []
    for r in regions:
        lawd = r["lawd"]; got = 0
        for ymd in months:
            try:
                items, err = parse(fetch(lawd, ymd, key))
            except Exception as ex:
                print(f"  · {r['이름']} {ymd}: 요청 실패 {ex}"); time.sleep(1); continue
            if err:
                print(f"  · {r['이름']} {ymd}: {err}")
                if "SERVICE" in err.upper() or "KEY" in err.upper():
                    print("  → 인증키 문제로 보입니다. 발급/등록 상태를 확인하세요."); sys.exit(1)
                time.sleep(0.4); continue
            for it in items:
                it["region"] = r["이름"]; it["lawd"] = lawd
            all_deals += items; got += len(items)
            time.sleep(0.3)
        print(f"  ✓ {r['이름']}: 거래 {got}건")

    # 단지 × 평형(전용㎡ 반올림) 으로 집계
    groups = defaultdict(list)
    for d in all_deals:
        groups[(d["region"], d["umd"], d["apt"], round(d["area"]))].append(d)

    candidates = []
    for (region, umd, apt, area), deals in groups.items():
        deals.sort(key=lambda x: x["date"], reverse=True)
        recent = deals[0]
        avg = round(sum(x["amount"] for x in deals) / len(deals))
        build = max(x["build"] for x in deals)
        supply = pyeong_supply(area)
        # 대표 지번(최빈) — 건축물대장 조회용
        from collections import Counter
        bb = Counter((d["bonbun"], d["bubun"]) for d in deals).most_common(1)[0][0]
        # 하드필터 (공공데이터로 판정 가능한 3개)
        if build < F["준공연도_최소"]: continue
        if recent["amount"] > F["매매최저가_최대_만원"]: continue
        if supply < F["공급면적_최소_평"]: continue
        lawd = deals[0]["lawd"]
        candidates.append({
            "단지번호": f"{lawd}-{umd}-{apt}-{area}",
            "단지명": apt, "주소": f"{region} {umd}",
            "법정동명": umd, "법정동코드5": lawd, "지번본번": bb[0], "지번부번": bb[1],
            "법정동읍면동코드": deals[0].get("umdCd"),  # 건축물대장 bjdongCd (리 단위까지)
            "매매최저가_만원": None,          # 현재 매물 호가 (수동 보강)
            "매물개수": None,
            "매물링크": "https://m.land.naver.com/search/result/"
                       + urllib.parse.quote(f"{apt} {umd}"),  # 네이버 부동산 매물 검색
            "층수": None,
            "실거래_직전_만원": recent["amount"], "실거래_평균_만원": avg,
            "실거래_거래일": recent["date"], "실거래_건수": len(deals),
            "대중교통_분": None, "대중교통_환승": None,   # 카카오맵 보강
            "준공연도": build, "용적률": None,            # K-apt 보강
            "대표평형_평": round(supply), "대표평형_공급_m2": round(supply*3.3058),
            "대표평형_전용_m2": area, "세대수": None,       # K-apt 보강
            "노후도_코멘트": None, "실리뷰_코멘트": None, "감성점수": None,
        })

    candidates.sort(key=lambda c: c["실거래_직전_만원"])
    out = {
        "_설명": "국토부 실거래가 기반 후보. 세대수·용적률·대중교통·리뷰는 이후 보강.",
        "샘플여부": False,
        "생성일시": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "기준역": CFG["기준역"]["이름"],
        "단지목록": candidates,
    }
    path = os.path.join(BASE, "data", "apartments.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n✅ 후보 {len(candidates)}개 저장 → {path}")
    print("상위 10개(실거래 낮은순):")
    for c in candidates[:10]:
        print(f"  - {c['단지명']} ({c['주소']}) {c['대표평형_전용_m2']}㎡/{c['대표평형_평']}평 "
              f"· 실거래 {c['실거래_직전_만원']/10000:.2f}억 · {c['준공연도']}년 · {c['실거래_건수']}건")

if __name__ == "__main__":
    main()
