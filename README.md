# 🏢 아파트 비교 분석 — 강남구청역 통근권

강남구청역 대중교통 60분 통근권(서울·경기)에서 **매매 5억 이하·저평가 아파트**를
공공데이터로 걸러 비교·추천하는 자동 갱신 대시보드.

**대시보드(GitHub Pages)**: 배포 후 URL이 여기에 표시됩니다.

## 필터 조건
매매 5억↓ · 강남구청역 대중교통 60분↓(ODsay 실측) · 준공 1996↑ · 용적률 250%↓ · 공급 20평↑(방2↑) · 50세대↑

## 데이터 출처 (전부 무료)
- **국토교통부 실거래가·건축물대장** (data.go.kr) — 실거래가·연식·면적·용적률·세대수·층수
- **ODsay 대중교통 길찾기** (lab.odsay.com) — 강남구청역까지 실측 소요시간·환승
- **네이버 부동산** — 단지 매물 링크

## 구조
| 파일 | 역할 |
|---|---|
| `run_all.sh` | 전체 파이프라인 실행 → 대시보드 생성 → 깃허브 배포 |
| `collect_molit.py` | 실거래가 수집 (국토부) |
| `collect_bldg.py` | 건축물대장 보강 (용적률·세대수·층수) + 하드필터 |
| `filter_distance.py` | 직선거리 사전필터 |
| `collect_transit.py` | ODsay 대중교통 실측 + 60분 필터 |
| `enrich_naver_links.py` | 네이버 단지ID·매물 링크 |
| `collect_asking.py` | 호가 수집(베스트에포트) |
| `gen_dashboard.py` | `dashboard.tmpl.html` → `dashboard.html`/`index.html` |
| `add_apartment.py` | 아파트 직접 추가(manual.json) |
| `config.json` | 설정·API키 (**로컬 전용, 커밋 안 함**) |

## 설정 (로컬)
1. `config.example.json` → `config.json` 복사
2. `config.json`에 API 키 입력:
   - `공공데이터.service_key`: data.go.kr 인증키
   - `대중교통.odsay_key`: ODsay 키 (Server 타입, 발급 IP 등록)
3. 실행: `bash run_all.sh`

## 자동 갱신
로컬 launchd(`com.aptcompare.dailyupdate`)가 매일 07:00 실행 → 데이터 갱신 →
`dashboard.html` 재생성 → 깃허브 push → GitHub Pages 자동 반영.

> 대시보드의 ⭐북마크·📝메모·🏷️호가·삭제는 브라우저 localStorage에 저장(개인별).
