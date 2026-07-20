# 🔄 다른 컴퓨터에서 이어서 작업하기 (인수인계)

이 프로젝트는 깃허브에 다 있어서 다른 컴퓨터에서 그대로 이어갈 수 있습니다.

## 현재 상태 (요약)
- **강남구청역 통근권 아파트 비교 대시보드** — 서울·경기 **164개 단지**
- 공개 URL: https://hyelaon.github.io/apt-compare/ (GitHub Pages)
- 데이터: 국토부 실거래가·건축물대장 + ODsay 대중교통(실측) — 전부 무료 공공/공개 API
- 각 단지: 실거래가·연식·평형·방개수·용적률·건폐율·세대수·층수·주차(세대당)·건축물용도·강남구청역 대중교통시간·매물링크
- 기능: 서울/경기남부/경기북부 지역필터, ⭐북마크·📝메모·🏷️호가입력·삭제(브라우저 저장), 직접추가
- **직접 추가된 4곳**(김포 분양단지, manual.json): 한강수자인오브센트·김포북변우미린파크리브·호반써밋풍무Ⅲ·김포칸타빌에디션

## 새 컴퓨터에서 세팅 (5단계)
1. **프로젝트 받기**: `git clone https://github.com/hyelaon/apt-compare.git && cd apt-compare`
2. **API 키 넣기**: `cp config.example.json config.json` 후 `config.json`에 키 2개 입력
   - `공공데이터.service_key`: data.go.kr 인증키 (아파트매매 상세 + 건축물대장 활용신청 필요)
   - `대중교통.odsay_key`: ODsay 키 (lab.odsay.com)
   - ⚠️ **config.json은 절대 깃허브에 커밋 금지** (.gitignore로 이미 제외됨) — 키는 손으로 옮기세요
3. **ODsay IP 갱신**: ODsay Server 키는 **발급 컴퓨터 공인 IP에 묶여 있음**. 새 컴퓨터에서 되게 하려면 lab.odsay.com 에서 등록 IP를 새 컴퓨터 IP로 바꾸거나 추가 (Claude에게 "공인 IP 확인해줘" 하면 알려줌)
4. **실행**: `bash run_all.sh` (데이터 갱신 + 대시보드 생성 + 깃허브 push)
5. **자동 갱신 예약(선택)**: 맥이면 launchd, 리눅스면 cron 으로 `run_all.sh` 매일 실행 (Claude가 설정 도와줌)

## Claude로 이어서 작업하려면
- 새 컴퓨터에서 **이 폴더(apt-compare)를 열고 Claude Code 실행** → 이 `HANDOFF.md`와 `README.md`를 읽으면 전체 맥락 파악됨
- 이어서 하고 싶은 걸 말하면 됨 (예: "지역 추가", "필터 바꿔줘", "호갱노노 링크 추가")

## 파이프라인 (run_all.sh 순서)
collect_molit(실거래) → collect_bldg(건축물대장, 캐시) → filter_distance(직선거리 사전컷) →
collect_transit(ODsay 실측+60분필터) → enrich_naver_links(매물수·링크) → collect_asking(호가 베스트에포트) → gen_dashboard(대시보드)

- 직접추가: `python3 add_hogangnono.py <호갱노노링크>` 또는 `python3 add_apartment.py --name --lawd --dong`
- 호가는 네이버 차단으로 자동수집 불가(링크로 확인). 남양주 읍/면은 MOLIT umdCd로 건축물대장 해결됨.

## 클라우드로 이미 접근 가능한 것 (컴퓨터 무관)
- 대시보드(웹): https://hyelaon.github.io/apt-compare/
- 소스·데이터: https://github.com/hyelaon/apt-compare
