#!/bin/bash
# 전체 파이프라인: 실거래 수집 → 건축물대장 보강/필터 → 대시보드 생성
cd "$(dirname "$0")"
echo "===== $(date '+%H:%M:%S') 시작 ====="
echo "[1/3] 실거래 수집 (28개 지역)"
python3 collect_molit.py 2>&1 | tail -35
echo
echo "[2/4] 건축물대장 보강 + 하드필터"
python3 collect_bldg.py 2>&1 | tail -20
echo
echo "[3/6] 직선거리 사전 보정(초광역 제외)"
python3 filter_distance.py 2>&1 | tail -3
echo
echo "[4/6] 강남구청역 대중교통 실측(ODsay) + 60분 필터"
python3 collect_transit.py 2>&1 | tail -5
echo
echo "[5/7] 네이버 단지ID 매칭(매물 링크)"
python3 enrich_naver_links.py 2>&1 | tail -3
echo
echo "[6/7] 호가 수집(fin.land, 베스트에포트 — 차단 시 건너뜀)"
python3 collect_asking.py 2>&1 | tail -3
echo
echo "[7/7] 대시보드 생성"
python3 gen_dashboard.py 2>&1

echo "[배포] GitHub Pages"
cp -f dashboard.html index.html
if git rev-parse --git-dir >/dev/null 2>&1 && git remote get-url origin >/dev/null 2>&1; then
  git add -A
  if git commit -m "auto: 데이터 갱신 $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1; then
    git push origin HEAD >/dev/null 2>&1 && echo "  ✓ 깃허브 push 완료" || echo "  · push 실패(네트워크/인증 확인)"
  else
    echo "  · 변경 없음"
  fi
else
  echo "  · git 미설정 — 배포 건너뜀"
fi
echo "===== $(date '+%H:%M:%S') 완료 ====="
