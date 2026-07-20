#!/usr/bin/env python3
"""
국토부 건축물대장(표제부) API로 후보 단지의 용적률·세대수·준공일 보강.
- 같은 data.go.kr 인증키 사용 (건축물대장정보 서비스 활용신청 필요)
- apartments.json 의 각 후보 지번으로 조회 → 용적률/세대수 채움
- 하드필터(용적률≤250, 세대수≥50, 대중교통≤60) 적용해 미달 단지 제외
사용: python3 collect_bldg.py
"""
import os, json, time, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
DBP = os.path.join(BASE, "data", "apartments.json")
DB = json.load(open(DBP, encoding="utf-8"))
KEY = os.environ.get("MOLIT_KEY") or CFG["공공데이터"].get("service_key", "")
F = CFG["하드필터"]

# 건축HUB: 표제부(동별) + 총괄표제부(단지 전체·용적률)
TITLE_EP = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
RECAP_EP = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept": "application/xml, */*", "Referer": "https://www.data.go.kr/"}

# 법정동 10자리 코드 맵 (build_regions.py 가 생성): { lawd: {umd: code10} }
_DC = json.load(open(os.path.join(BASE, "data", "dong_codes.json"), encoding="utf-8"))
DONGMAP = {lawd: v.get("dongs", {}) for lawd, v in _DC.items()}
_CACHE = {}  # (ep, sig, bj, bun, ji) -> body  (런 내 중복 지번 재요청 방지)

# 영구 캐시: 건축물대장은 정적 데이터라 지번별 결과를 저장해 매일 재조회 방지
PCACHE_PATH = os.path.join(BASE, "data", "bldg_cache.json")
PCACHE = json.load(open(PCACHE_PATH, encoding="utf-8")) if os.path.exists(PCACHE_PATH) else {}

def get_bldg(sig, bj, bun, ji):
    """지번별 용적률·세대수·층수 (영구 캐시 우선)."""
    k = f"{sig}|{bj}|{bun}|{ji}"
    if k in PCACHE:
        return PCACHE[k]
    body = fetch(TITLE_EP, sig, bj, bun, ji)
    if body is None:
        return None
    info, err = parse(body)
    if err:
        return {"_err": err}
    rbody = fetch(RECAP_EP, sig, bj, bun, ji, tries=3)
    recap = parse_recap(rbody) if rbody else {}
    res = {"용적률": recap.get("용적률") or info["용적률"],
           "세대수": recap.get("세대수") or info["세대수"],
           "층수": info.get("층수") or recap.get("층수")}
    PCACHE[k] = res
    return res

def fetch(ep, sigungu, bjdong, bun, ji, tries=5):
    # 방화벽 간헐적 403 대비 재시도. _type=xml 필수. 결과 캐시.
    ck = (ep, sigungu, bjdong, bun, ji)
    if ck in _CACHE:
        return _CACHE[ck]
    sk = KEY if "%" in KEY else urllib.parse.quote(KEY, safe="")
    url = (f"{ep}?serviceKey={sk}&sigunguCd={sigungu}&bjdongCd={bjdong}"
           f"&platGbCd=0&bun={bun}&ji={ji}&numOfRows=100&pageNo=1&_type=xml")
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read().decode("utf-8", "replace")
            if body.lstrip().startswith("<") and "resultCode" in body:
                return body
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 500):
                time.sleep(0.6 * (i + 1)); continue
        except Exception:
            time.sleep(0.6 * (i + 1)); continue
        time.sleep(0.5)
    return None

def parse(xml_text):
    root = ET.fromstring(xml_text)
    code = root.findtext(".//resultCode")
    if code not in (None, "00", "000"):
        return None, root.findtext(".//resultMsg") or f"코드 {code}"
    items = root.findall(".//item")
    apt = [it for it in items if "공동주택" in (it.findtext("mainPurpsCdNm") or "")]
    use = apt or items  # 공동주택 표제부 없으면 전체(근생 등)로 폴백
    vlrat, hh, flr = None, 0, None
    for it in use:
        g = lambda t: (it.findtext(t) or "").strip()
        try:
            v = float(g("vlRat") or 0)
            if v: vlrat = max(vlrat or 0, v)
        except ValueError: pass
        try:
            hh += int(float(g("hhldCnt") or 0))
        except ValueError: pass
        try:
            f = int(float(g("grndFlrCnt") or 0))
            if f: flr = max(flr or 0, f)  # 지상 최고 층수
        except ValueError: pass
    return {"용적률": round(vlrat) if vlrat else None, "세대수": hh or None, "층수": flr}, None

def parse_recap(xml_text):
    # 총괄표제부: 단지 전체 용적률·총세대수 (단일 item)
    root = ET.fromstring(xml_text)
    if root.findtext(".//resultCode") not in (None, "00", "000"):
        return {}
    it = root.find(".//item")
    if it is None: return {}
    g = lambda t: (it.findtext(t) or "").strip()
    out = {}
    try:
        v = float(g("vlRat") or 0)
        if v: out["용적률"] = round(v)
    except ValueError: pass
    try:
        h = int(float(g("hhldCnt") or 0))
        if h: out["세대수"] = h
    except ValueError: pass
    try:
        f = int(float(g("grndFlrCnt") or 0))
        if f: out["층수"] = f
    except ValueError: pass
    return out

def main():
    if not KEY:
        print("❌ 인증키 없음"); return
    apts = DB["단지목록"]
    ok = 0; fail = 0
    for a in apts:
        dong10 = DONGMAP.get(a["법정동코드5"], {}).get(a.get("법정동명", ""))
        if not dong10:
            print(f"  ? {a['단지명']}: 동코드 없음({a.get('법정동명')})"); fail += 1; continue
        sig = a["법정동코드5"]; bj = dong10[5:]
        bun = str(a["지번본번"]).zfill(4); ji = str(a["지번부번"]).zfill(4)
        res = get_bldg(sig, bj, bun, ji)
        if res is None:
            print(f"  · {a['단지명']}: 조회 실패(재시도 소진)"); fail += 1; continue
        if res.get("_err"):
            print(f"  · {a['단지명']}: {res['_err']}")
            if any(k in res['_err'].upper() for k in ("SERVICE", "KEY")) or "등록" in res['_err']:
                print("  → 건축물대장 API 활용신청/승인 상태를 확인하세요."); return
            fail += 1; continue
        a["용적률"] = res["용적률"]; a["세대수"] = res["세대수"]; a["층수"] = res["층수"]
        age = 2026 - a.get("준공연도", 2026)
        a["노후도_코멘트"] = (f"{a['준공연도']}년 준공(약 {age}년차) — "
                        + ("준신축·양호" if age<=10 else "중간 연식" if age<=20 else "노후 진행"))
        ok += 1
        time.sleep(0.05)

    # 단지 내 값 전파(같은 법정동·단지명끼리 채움)
    best = {}
    FIELDS = ("용적률", "세대수", "층수")
    for a in apts:
        k = (a["법정동코드5"], a["단지명"])
        if any(a.get(x) is not None for x in FIELDS):
            best.setdefault(k, {}).update({x: a[x] for x in FIELDS if a.get(x) is not None})
    for a in apts:
        b = best.get((a["법정동코드5"], a["단지명"]), {})
        for x in FIELDS:
            if a.get(x) is None and x in b: a[x] = b[x]

    json.dump(PCACHE, open(PCACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n보강 완료: 성공 {ok} · 실패 {fail} · 캐시 {len(PCACHE)}건")

    # 하드필터 적용 → 조건 미달 제외 (값을 아는 경우만 제외; 모르면 '미확인'으로 보존)
    kept, dropped = [], []
    for a in apts:
        reasons = []
        if a.get("용적률") is not None and a["용적률"] > F["용적률_최대_퍼센트"]:
            reasons.append(f"용적률 {a['용적률']}%>250")
        if a.get("세대수") is not None and a["세대수"] < F["세대수_최소"]:
            reasons.append(f"세대 {a['세대수']}<50")
        if a.get("대중교통_분") is not None and a["대중교통_분"] > F["강남구청역_대중교통_최대_분"]:
            reasons.append(f"교통 {a['대중교통_분']}분>60")
        a["검증"] = "확인" if (a.get("용적률") is not None and a.get("세대수") is not None) else "일부미확인"
        (dropped if reasons else kept).append((a, reasons))

    DB["단지목록"] = [a for a, _ in kept]
    DB["생성일시"] = DB.get("생성일시", "")
    json.dump(DB, open(DBP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n제외 {len(dropped)}개:")
    for a, rs in dropped:
        print(f"  - {a['단지명']}: {', '.join(rs)}")
    print(f"남은 후보: {len(DB['단지목록'])}개")

if __name__ == "__main__":
    main()
