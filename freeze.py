"""GitHub Pages 용 정적 사이트 생성:  python freeze.py  ->  docs/ 폴더 (모든 파일이 한 폴더에 평평하게 저장됨).
인증키는 결과물에 들어가지 않는다 (API 호출은 이 스크립트를 돌리는 내 PC에서만 일어남)."""
import shutil
from pathlib import Path

import app as web
import services

import os
import sys

if os.getenv("GITHUB_ACTIONS") and not services.KEY:  # 키 없이 샘플 데이터가 배포되는 사고 방지
    sys.exit("DATA_GO_KR_KEY 비밀값이 없습니다. 저장소 Settings > Secrets > Actions 에 등록하세요.")

OUT = Path(__file__).parent / "docs"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
web.STATIC_EXPORT = True
client = web.app.test_client()

failed = []
for stn in services.STATIONS:
    try:
        arts, _ = services.build_articles(stn)
        (OUT / web.href("index", stn)).write_bytes(client.get(f"/?stn={stn}").data)
        for a in arts:
            (OUT / web.href("article", stn, a["slug"])).write_bytes(client.get(f"/a/{a['slug']}?stn={stn}").data)
        print("OK", stn, services.STATIONS[stn])
    except Exception as e:  # 한 지점 실패가 전체 배포를 막지 않게 (서울은 필수)
        print("실패", stn, type(e).__name__)
        failed.append(stn)
        if stn == "108":
            sys.exit("서울(108) 데이터를 받지 못해 배포를 중단합니다.")
if failed:
    print("건너뛴 지점:", failed)

shutil.copy(Path(__file__).parent / "static" / "style.css", OUT / "style.css")
for p in (Path(__file__).parent / "static" / "photos").glob("*.jpg"):
    shutil.copy(p, OUT / ("p-" + p.name))
(OUT / ".nojekyll").write_text("")
print(len(list(OUT.iterdir())), "files ->", OUT)
