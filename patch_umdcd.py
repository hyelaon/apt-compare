#!/usr/bin/env python3
"""
기존 apartments.json 후보에 법정동읍면동코드(umdCd)를 소급 채움.
MOLIT 실거래에서 (법정동명 → umdCd) 맵만 뽑아 매칭. 건축물대장 리(里) 조회용.
"""
import os, json, time
import collect_molit as M

BASE = os.path.dirname(os.path.abspath(__file__))
DBP = os.path.join(BASE, "data", "apartments.json")
DB = json.load(open(DBP, encoding="utf-8"))
key = M.service_key()

needed = {}
for a in DB["단지목록"]:
    if not a.get("법정동읍면동코드"):
        needed.setdefault(a["법정동코드5"], set()).add(a["법정동명"])

codemap = {}
for lawd, umds in needed.items():
    found = {}
    for ymd in M.recent_months(12):
        items, err = M.parse(M.fetch(lawd, ymd, key))
        if err:
            time.sleep(0.3); continue
        for it in items:
            u = it["umd"]
            if u in umds and u not in found and it.get("umdCd"):
                found[u] = it["umdCd"]
        if len(found) >= len(umds):
            break
        time.sleep(0.25)
    for u, c in found.items():
        codemap[(lawd, u)] = c
    print(f"  {lawd}: {len(found)}/{len(umds)} 동코드 확보")

n = 0
for a in DB["단지목록"]:
    if not a.get("법정동읍면동코드"):
        c = codemap.get((a["법정동코드5"], a["법정동명"]))
        if c:
            a["법정동읍면동코드"] = c; n += 1

json.dump(DB, open(DBP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"umdCd 채움: {n}개")
