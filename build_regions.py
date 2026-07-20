#!/usr/bin/env python3
"""
config 의 active 지역 lawd(5자리)를 검증하고, 각 지역의 법정동 10자리 코드 맵을 만든다.
네이버 지역 API(getRegionList) 사용 — 인증키 불필요.
결과: data/dong_codes.json = { lawd: { "구명": ..., "dongs": { 동명: 10자리코드 } } }
"""
import os, json, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://m.land.naver.com/"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

out = {}
for reg in CFG["대상권역"]["목록"]:
    if reg.get("status") != "active":
        continue
    lawd = reg["lawd"]; gu_cortar = lawd + "00000"
    try:
        d = get(f"https://m.land.naver.com/map/getRegionList?cortarNo={gu_cortar}")
        info = d.get("result", {})
        sec = info.get("dvsnInfo", {}) or info.get("secInfo", {})
        gunm = sec.get("CortarNm", "")
        dongs = {x["CortarNm"]: x["CortarNo"] for x in info.get("list", [])}
        coords = {x["CortarNm"]: [float(x.get("MapYCrdn", 0)), float(x.get("MapXCrdn", 0))]
                  for x in info.get("list", [])}  # [위도, 경도]
        out[lawd] = {"이름": reg["이름"], "구명": gunm, "dongs": dongs, "coords": coords}
        flag = "✓" if dongs else "⚠️(동 없음)"
        print(f"  {flag} {reg['이름']:12s} lawd={lawd} → {gunm} · 동 {len(dongs)}개")
    except Exception as ex:
        print(f"  ✗ {reg['이름']} lawd={lawd}: {ex}")
    time.sleep(0.3)

json.dump(out, open(os.path.join(BASE, "data", "dong_codes.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\n저장: data/dong_codes.json ({len(out)}개 지역)")
