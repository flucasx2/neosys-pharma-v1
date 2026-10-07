from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from neosys_pharma.presentation.organisation_api import router
from neosys_pharma.presentation.equipement_api import router as equipement_router


from neosys_pharma.presentation.securite_api import router as securite_router


from neosys_pharma.presentation.authentification_api import router as auth_router
from neosys_pharma.presentation.acces import require_access
from neosys_pharma.presentation.catalogue_api import router as catalogue_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="NeoSys Pharma",
        version="0.1.0",
    )
    app.include_router(router, dependencies=[Depends(require_access)])
    app.include_router(equipement_router, dependencies=[Depends(require_access)])
    app.include_router(securite_router, dependencies=[Depends(require_access)])
    app.include_router(auth_router)
    app.include_router(catalogue_router)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo password input in validation responses.
        errors=[{"loc":e["loc"],"msg":e["msg"],"type":e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422,content={"detail":errors})

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response=await call_next(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers["Referrer-Policy"]="same-origin"
        return response

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
