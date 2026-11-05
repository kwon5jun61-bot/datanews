"""공공데이터포털 API 호출 + 기사 생성 로직."""
import hashlib
import os
import random
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")
KEY = os.getenv("DATA_GO_KR_KEY", "").strip()

PHOTO_DIR = BASE / "static" / "photos"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

STATIONS = {"108": "서울", "112": "인천", "119": "수원", "133": "대전", "143": "대구",
            "156": "광주", "159": "부산", "184": "제주"}

ASOS_URL = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
PHOTO_URL = "https://apis.data.go.kr/B551011/PhotoGalleryService1/gallerySearchList1"

def _get(url, **kw):
    """해외(GitHub 서버)에서 호출하면 공공데이터포털 응답이 느릴 수 있어 재시도한다."""
    last = None
    for i in range(4):
        try:
            r = requests.get(url, timeout=kw.pop("timeout", 60) if i == 0 else 60, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


_cache: dict = {}
TTL = 3600  # 1시간 캐시 (API 호출 횟수 절약)


def _cached(key, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


# ---------------------------------------------------------------- 기상청 ASOS
def _fetch_weather(stn: str, days: int = 30):
    end = date.today() - timedelta(days=2)  # 최근 1~2일은 자료가 비어 있을 수 있음
    start = end - timedelta(days=days - 1)
    if not KEY:  # 키가 없으면 샘플 데이터
        rnd = random.Random(1)
        rows = []
        for i in range(days):
            a = round(12 + 5 * __import__("math").sin(i / 5) + rnd.random() * 2, 1)
            rows.append({"d": (start + timedelta(days=i)).isoformat(), "avg": a, "min": round(a - 4, 1),
                         "max": round(a + 5, 1), "rain": round(rnd.random() * 30, 1) if rnd.random() > .75 else 0.0})
        return rows, True
    r = _get(ASOS_URL, params={
        "serviceKey": KEY, "pageNo": 1, "numOfRows": days + 10, "dataType": "JSON", "dataCd": "ASOS",
        "dateCd": "DAY", "startDt": start.strftime("%Y%m%d"), "endDt": end.strftime("%Y%m%d"), "stnIds": stn})
    r.raise_for_status()
    items = r.json()["response"]["body"]["items"]["item"]
    f = lambda v: float(v) if v not in (None, "") else None
    rows = []
    for i in items:
        if None in (f(i.get("avgTa")), f(i.get("minTa")), f(i.get("maxTa"))):
            continue
        rows.append({"d": i["tm"], "avg": f(i["avgTa"]), "min": f(i["minTa"]), "max": f(i["maxTa"]),
                     "rain": f(i.get("sumRn")) or 0.0})
    return rows, False


def get_weather(stn: str):
    return _cached(("w", stn), lambda: _fetch_weather(stn))


# ------------------------------------------------- 한국관광공사 관광사진
def _fetch_photo(keyword: str):
    """키워드로 검색한 첫 사진을 static/photos 에 저장하고 URL 경로를 돌려준다."""
    if not KEY:
        return None
    # 날짜가 파일명에 들어가므로 하루에 한 번 새로 받는다 (최신 등록 사진)
    fname = hashlib.md5(f"{keyword}-{date.today()}".encode()).hexdigest()[:10] + ".jpg"
    for old in PHOTO_DIR.glob("*.jpg"):  # 지난 날짜 사진 정리
        if old.name != fname and time.time() - old.stat().st_mtime > 3 * 86400:
            old.unlink()
    path = PHOTO_DIR / fname
    if path.exists():
        return f"/static/photos/{fname}"
    try:
        r = _get(PHOTO_URL, params={
            "serviceKey": KEY, "numOfRows": 5, "pageNo": 1, "MobileOS": "ETC", "MobileApp": "datanews",
            "arrange": "D", "_type": "json", "keyword": keyword})  # D = 생성일(최신 등록) 순
        r.raise_for_status()
        items = r.json()["response"]["body"]["items"]
        items = items["item"] if items else []
        items = items if isinstance(items, list) else [items]
        url = next((i["galWebImageUrl"] for i in items if i.get("galWebImageUrl")), None)
        if not url:
            return None
        path.write_bytes(_get(url).content)
        return f"/static/photos/{fname}"
    except Exception as e:  # 사진은 없어도 기사는 보여준다
        print("사진 조회 실패:", keyword, str(e).replace(KEY, "***"))
        return None


def get_photo(keyword: str):
    return _cached(("p", keyword), lambda: _fetch_photo(keyword))


# ----------------------------------------------------------------- 기사 생성
def _season_kw(d: date):
    m = d.month
    return "벚꽃" if m in (3, 4, 5) else "바다" if m in (6, 7, 8) else "단풍" if m in (9, 10, 11) else "설경"


def build_articles(stn: str):
    city = STATIONS.get(stn, stn)
    rows, demo = get_weather(stn)
    if not rows:
        raise RuntimeError("관측 데이터가 없습니다.")
    n = len(rows)
    avg_all = round(sum(r["avg"] for r in rows) / n, 1)
    hot = max(rows, key=lambda r: r["max"])
    cold = min(rows, key=lambda r: r["min"])
    wet = max(rows, key=lambda r: r["rain"])
    rain_days = sum(1 for r in rows if r["rain"] > 0)
    rain_sum = round(sum(r["rain"] for r in rows), 1)
    ranges = [round(r["max"] - r["min"], 1) for r in rows]
    avg_range = round(sum(ranges) / n, 1)
    wide_i = max(range(n), key=lambda i: ranges[i])
    first, last = rows[0]["avg"], rows[-1]["avg"]
    trend = "올랐다" if last > first else "내렸다"
    period = f"{rows[0]['d']} ~ {rows[-1]['d']}"
    labels = [r["d"][-5:] for r in rows]
    end_d = date.fromisoformat(rows[-1]["d"])

    meta = dict(city=city, period=period, stn=stn, demo=demo, days=n)
    arts = [
        dict(slug="temp", cat="기상", cat2="기온", photo_kw=_season_kw(end_d),
             title=f"{city}, 최근 {n}일 평균기온 {avg_all}℃… 기온은 {first}℃에서 {last}℃로 {trend}",
             lead=f"[데이터 브리핑] 가장 더웠던 날은 {hot['d']}, 가장 추웠던 날은 {cold['d']}였다. {n}일간 기온은 어떻게 움직였나.",
             toc=[f"평균기온 {avg_all}℃", "더웠던 날과 추웠던 날"],
             sections=[
                 (f"평균기온 {avg_all}℃",
                  f"기상청 종관기상관측(ASOS) 자료에 따르면 {period} 기간 {city}의 일평균기온은 {avg_all}℃로 집계됐다. "
                  f"기간 첫날 평균기온은 {first}℃, 마지막 날은 {last}℃로 한 달 사이 {trend}.", True),
                 ("더웠던 날과 추웠던 날",
                  f"가장 더웠던 날은 <b>{hot['d']}</b>로 최고기온이 {hot['max']}℃까지 올랐다. "
                  f"반대로 가장 추웠던 날은 <b>{cold['d']}</b>로 최저기온 {cold['min']}℃를 기록했다.", False)],
             chart=dict(type="line", labels=labels, datasets=[
                 dict(label="최고", data=[r["max"] for r in rows], borderColor="#e53e3e", pointRadius=0, tension=.3),
                 dict(label="평균", data=[r["avg"] for r in rows], borderColor="#1a202c", pointRadius=0, tension=.3),
                 dict(label="최저", data=[r["min"] for r in rows], borderColor="#3182ce", pointRadius=0, tension=.3)])),
        dict(slug="rain", cat="기상", cat2="강수", photo_kw="폭포",
             title=f"{city}, {n}일간 비 온 날 {rain_days}일… 누적 강수량 {rain_sum}mm",
             lead=f"[데이터 브리핑] 가장 많은 비가 내린 날은 {wet['d']}로 {wet['rain']}mm였다. 한 달 강수를 날짜별로 살펴봤다.",
             toc=[f"비 온 날 {rain_days}일", "가장 비가 많았던 날"],
             sections=[
                 (f"비 온 날 {rain_days}일",
                  f"{period} {n}일 동안 {city}에서 강수가 기록된 날은 {rain_days}일, 누적 강수량은 {rain_sum}mm였다.", True),
                 ("가장 비가 많았던 날", f"일 강수량이 가장 컸던 날은 <b>{wet['d']}</b>로 {wet['rain']}mm가 내렸다.", False)],
             chart=dict(type="bar", labels=labels, datasets=[
                 dict(label="강수량(mm)", data=[r["rain"] for r in rows], backgroundColor="#4299e1")])),
        dict(slug="range", cat="기상", cat2="일교차", photo_kw="안개",
             title=f"{city} 평균 일교차 {avg_range}℃… 가장 컸던 날은 {rows[wide_i]['d']}",
             lead=f"[데이터 브리핑] 하루 중 최고기온과 최저기온의 차이, 일교차가 가장 컸던 날은 {ranges[wide_i]}℃였다.",
             toc=[f"평균 일교차 {avg_range}℃", "일교차가 가장 컸던 날"],
             sections=[
                 (f"평균 일교차 {avg_range}℃", f"{period} 기간 {city}의 하루 평균 일교차는 {avg_range}℃였다.", True),
                 ("일교차가 가장 컸던 날",
                  f"<b>{rows[wide_i]['d']}</b>에는 일교차가 {ranges[wide_i]}℃에 달했다. 큰 일교차는 건강관리에 주의가 필요한 신호로 읽힌다.", False)],
             chart=dict(type="bar", labels=labels, datasets=[
                 dict(label="일교차(℃)", data=ranges, backgroundColor="#ed8936")])),
    ]
    for a in arts:
        a["photo"] = get_photo(a["photo_kw"])
    return arts, meta
