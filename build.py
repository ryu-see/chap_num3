#!/usr/bin/env python3
"""
청렴 신고 조회 페이지 빌드 스크립트 (표준 라이브러리만 사용)

하는 일
  1. data/*.csv  ->  dist/data/*.json  변환
  2. Google 뉴스 RSS에서 최신 5건을 가져와 dist/data/news.json 저장
     (가져오지 못하면 직전 빌드의 news.json을 그대로 사용)
  3. template.html 에 사건 데이터와 뉴스 목록(정적 HTML)을 넣어 dist/index.html 생성

실행
  python3 build.py
  python3 build.py --query "청렴 부패 신고"   # RSS 검색어 변경
"""
import argparse
import csv
import html
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data"
DIST = ROOT / "dist"
DIST_DATA = DIST / "data"

CASES_CSV = SRC / "청렴신고_사건데이터.csv"
EDU_CSV = SRC / "청렴교육_현황.csv"

DEFAULT_QUERY = "청렴 신고"
NEWS_LIMIT = 5


# ---------------------------------------------------------------- CSV -> JSON
def _num(value, kind):
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return kind(value)
    except ValueError:
        return None


def read_csv(path):
    # utf-8-sig : 첫 열 이름 앞의 BOM 제거
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_cases():
    cases = []
    for r in read_csv(CASES_CSV):
        cases.append({
            "id": r["사건ID"].strip(),
            "date": r["신고일자"].strip(),
            "type": r["신고유형"].strip(),
            "region": r["지역"].strip(),
            "reporter": r["신고자유형"].strip(),
            "status": r["처리상태"].strip(),
            "days": _num(r["처리기간_일"], int),
            "amount": _num(r["위반금액_만원"], int),   # 단위: 만원
            "result": r["조치결과"].strip(),
        })
    cases.sort(key=lambda c: (c["date"], c["id"]), reverse=True)  # 최신순
    return cases


def load_education():
    rows = []
    for r in read_csv(EDU_CSV):
        rows.append({
            "code": r["기관코드"].strip(),
            "name": r["기관명"].strip(),
            "orgType": r["기관유형"].strip(),
            "completionRate": _num(r["교육이수율"], float),
            "hours": _num(r["연간교육시간"], int),
            "participants": _num(r["교육참여자수"], int),
            "excellent": r["청렴우수기관"].strip() == "Y",
        })
    return rows


# ---------------------------------------------------------- Google News RSS
def rss_url(query):
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


def fetch_news(url, limit=NEWS_LIMIT):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (integrity-site build)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        root = ET.fromstring(resp.read())

    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        # Google 뉴스 제목은 "기사 제목 - 언론사" 형태 → 언론사 꼬리 제거
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        pub = it.findtext("pubDate") or ""
        try:
            dt = parsedate_to_datetime(pub)
        except (TypeError, ValueError):
            dt = None
        if title and link.startswith(("http://", "https://")):
            items.append({"title": title, "link": link, "source": source,
                          "published": dt.isoformat() if dt else None, "_dt": dt})

    items.sort(key=lambda x: x["_dt"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    for x in items:
        x.pop("_dt")
    return items[:limit]


def load_news(query):
    url = rss_url(query)
    cache = DIST_DATA / "news.json"
    try:
        items = fetch_news(url)
        payload = {"source": url, "query": query,
                   "fetchedAt": datetime.now(timezone.utc).isoformat(), "items": items}
        print(f"[news] RSS {len(items)}건 수집")
    except Exception as e:  # 네트워크 차단, 파싱 오류 등
        print(f"[news] RSS 수집 실패: {e}", file=sys.stderr)
        if cache.exists():
            payload = json.loads(cache.read_text(encoding="utf-8"))
            payload["source"] = url
            print("[news] 직전 빌드의 news.json 사용")
        else:
            payload = {"source": url, "query": query, "fetchedAt": None, "items": []}
    return payload


def render_news(news):
    if not news["items"]:
        return '<li class="news-empty">빌드 시점에 뉴스를 가져오지 못했습니다. 아래 출처 링크에서 직접 확인하세요.</li>'
    out = []
    for n in news["items"]:
        date = n["published"][:10] if n.get("published") else ""
        meta = " · ".join(x for x in (html.escape(n.get("source", "")), date) if x)
        out.append(
            f'<li><a href="{html.escape(n["link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'{html.escape(n["title"])}</a><span class="news-meta">{meta}</span></li>'
        )
    return "\n        ".join(out)


# --------------------------------------------------------------------- build
def option_tags(values):
    return "\n            ".join(
        f'<option value="{html.escape(v, quote=True)}">{html.escape(v)}</option>' for v in values
    )


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default=DEFAULT_QUERY, help="Google 뉴스 RSS 검색어")
    args = ap.parse_args()

    DIST_DATA.mkdir(parents=True, exist_ok=True)

    cases = load_cases()
    write_json(DIST_DATA / "cases.json", cases)
    write_json(DIST_DATA / "education.json", load_education())

    news = load_news(args.query)
    write_json(DIST_DATA / "news.json", news)

    type_order = ["금품수수", "직권남용", "예산횡령", "이해충돌", "공금유용", "기타"]
    status_order = ["접수완료", "조사중", "처리완료", "이첩", "기각"]
    types = [t for t in type_order if any(c["type"] == t for c in cases)]
    types += sorted({c["type"] for c in cases} - set(types))
    statuses = [s for s in status_order if any(c["status"] == s for c in cases)]
    statuses += sorted({c["status"] for c in cases} - set(statuses))

    # 페이지에서 쓰는 필드만 인라인 (file:// 로 열어도 동작하도록)
    slim = [{k: c[k] for k in ("id", "date", "type", "region", "status")} for c in cases]
    inline_json = json.dumps(slim, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    built_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = (ROOT / "template.html").read_text(encoding="utf-8")
    replacements = {
        "{{TYPE_OPTIONS}}": option_tags(types),
        "{{STATUS_OPTIONS}}": option_tags(statuses),
        "{{CASES_JSON}}": inline_json,
        "{{TOTAL}}": str(len(cases)),
        "{{NEWS_ITEMS}}": render_news(news),
        "{{NEWS_SOURCE}}": html.escape(news["source"], quote=True),
        "{{NEWS_QUERY}}": html.escape(news.get("query", args.query)),
        "{{BUILT_AT}}": built_at,
    }
    for key, val in replacements.items():
        page = page.replace(key, val)
    (DIST / "index.html").write_text(page, encoding="utf-8")

    print(f"[build] 사건 {len(cases)}건 → dist/index.html, dist/data/*.json")


if __name__ == "__main__":
    main()
