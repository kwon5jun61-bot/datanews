"""GitHub Pages 용 정적 사이트 생성:  python freeze.py  ->  docs/ 폴더 (모든 파일이 한 폴더에 평평하게 저장됨).
인증키는 결과물에 들어가지 않는다 (API 호출은 이 스크립트를 돌리는 내 PC에서만 일어남)."""
import shutil
from pathlib import Path

import app as web
import services

OUT = Path(__file__).parent / "docs"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
web.STATIC_EXPORT = True
client = web.app.test_client()

for stn in services.STATIONS:
    arts, _ = services.build_articles(stn)
    (OUT / web.href("index", stn)).write_bytes(client.get(f"/?stn={stn}").data)
    for a in arts:
        (OUT / web.href("article", stn, a["slug"])).write_bytes(client.get(f"/a/{a['slug']}?stn={stn}").data)
    print("OK", stn, services.STATIONS[stn])

shutil.copy(Path(__file__).parent / "static" / "style.css", OUT / "style.css")
for p in (Path(__file__).parent / "static" / "photos").glob("*.jpg"):
    shutil.copy(p, OUT / ("p-" + p.name))
(OUT / ".nojekyll").write_text("")
print(len(list(OUT.iterdir())), "files ->", OUT)
