"""데이터뉴스 - 공공데이터 API 기반 기사 서비스.  실행: python app.py"""
from datetime import datetime

from flask import Flask, abort, render_template, request, url_for

import services

app = Flask(__name__)


def _load():
    stn = request.args.get("stn", "108")
    if stn not in services.STATIONS:
        stn = "108"
    try:
        return services.build_articles(stn)
    except Exception as e:  # API 오류는 화면에 안내
        app.logger.error("데이터 로드 실패: %s", str(e).replace(services.KEY or "-", "***"))
        abort(502, "공공데이터 API 호출에 실패했습니다. 잠시 후 다시 시도하세요.")


STATIC_EXPORT = False  # freeze.py 가 True 로 바꿔 GitHub Pages 용 정적 파일을 만든다


def href(kind, stn, slug=None):
    """동적 서버: Flask 주소 / 정적 내보내기: 한 폴더에 평평하게 저장되는 파일명."""
    if STATIC_EXPORT:
        if kind == "index":
            return "index.html" if stn == "108" else f"{stn}.html"
        return f"{stn}-{slug}.html"
    return url_for("index", stn=stn) if kind == "index" else url_for("article", slug=slug, stn=stn)


def asset(path):
    if STATIC_EXPORT:
        name = path.rsplit("/", 1)[-1]
        return "p-" + name if "/photos/" in path else name
    return path if path.startswith("/") else url_for("static", filename=path)


@app.context_processor
def common():
    return dict(stations=services.STATIONS, now=datetime.now(), href=href, asset=asset)


@app.route("/")
def index():
    arts, meta = _load()
    return render_template("index.html", arts=arts, meta=meta)


@app.route("/a/<slug>")
def article(slug):
    arts, meta = _load()
    art = next((a for a in arts if a["slug"] == slug), None)
    if not art:
        abort(404)
    return render_template("article.html", a=art, others=[x for x in arts if x is not art], meta=meta)


@app.errorhandler(502)
@app.errorhandler(404)
def err(e):
    return render_template("error.html", msg=getattr(e, "description", "")), e.code


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
