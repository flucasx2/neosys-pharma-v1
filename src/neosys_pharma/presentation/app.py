from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from neosys_pharma.presentation.organisation_api import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="NeoSys Pharma",
        version="0.1.0",
    )
    app.include_router(router)
    web = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=web), name="static")

    @app.get("/", include_in_schema=False)
    def organisation_interface():
        return FileResponse(web / "index.html")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "application": "NeoSys Pharma",
        }

    return app


app = create_app()
