# 청렴 신고 사건 조회 (정적 웹페이지)

## 구성
```
integrity-site/
├─ build.py          # CSV → JSON 변환, Google 뉴스 RSS 수집, index.html 생성
├─ template.html     # 페이지 템플릿 ({{...}} 자리에 빌드 결과가 들어감)
├─ data/             # 원본 CSV
│  ├─ 청렴신고_사건데이터.csv
│  └─ 청렴교육_현황.csv
└─ dist/             # 빌드 결과 (이 폴더만 배포)
   ├─ index.html
   └─ data/cases.json, education.json, news.json
```

## 빌드
Python 3.8 이상, 외부 패키지 없음.
```
python3 build.py                       # 기본 검색어 "청렴 신고"
python3 build.py --query "청렴 부패"    # RSS 검색어 변경
```
빌드할 때 Google 뉴스 RSS
(`https://news.google.com/rss/search?q=청렴+신고&hl=ko&gl=KR&ceid=KR:ko`)
에서 최신 5건을 가져와 HTML 안에 정적 목록으로 넣습니다.
네트워크 오류로 실패하면 직전 빌드의 `dist/data/news.json`을 다시 쓰고,
그것도 없으면 안내 문구와 RSS 출처 링크만 표시합니다.

## 배포
`dist/` 폴더를 GitHub Pages, Netlify 등 정적 호스팅에 올리면 됩니다.
사건 데이터가 HTML 안에 들어 있어 `index.html`을 파일로 바로 열어도 동작합니다.
뉴스를 주기적으로 갱신하려면 `python3 build.py`를 CI(예: GitHub Actions 일 1회)로 실행하세요.

## 기능
- `<title>청렴 신고 사건 조회</title>`
- 사건 카드: 신고일자 · 신고유형 · 지역 · 처리상태 (최신순, 30건씩 더 보기)
- 필터: 신고유형 / 처리상태 (조합 가능, URL `?type=금품수수&status=조사중` 으로 공유 가능)
- "결과 N건" 실시간 표시
- 사이드바: Google 뉴스 RSS 최신 5건 + 출처 링크
