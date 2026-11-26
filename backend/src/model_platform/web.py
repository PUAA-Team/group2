from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def attach_web(app):
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    web_dist = frontend / "web" / "dist"
    # 只提供显式的前端资源目录，不把工作区、数据库或文档目录挂到网页。
    app.mount("/assets", StaticFiles(directory=web_dist / "assets", check_dir=False), name="web-assets")
    for name in ("live", "styles", "js"):
        app.mount(f"/{name}", StaticFiles(directory=frontend / name, check_dir=False), name=f"web-{name}")

    @app.get("/", include_in_schema=False)
    def index():
        dist_index = web_dist / "index.html"
        target = dist_index if dist_index.is_file() else (frontend / "live" / "index.html")
        return FileResponse(target, headers={"Cache-Control": "no-store"})
