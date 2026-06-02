"""Health check route."""


def healthz() -> dict:
    return {"status": "ok"}


async def handle_healthz():
    from fastapi.responses import JSONResponse
    return JSONResponse(content=healthz(), status_code=200)
