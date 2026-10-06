from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="NeoSys Pharma",
        version="0.1.0",
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "application": "NeoSys Pharma",
        }

    return app


app = create_app()