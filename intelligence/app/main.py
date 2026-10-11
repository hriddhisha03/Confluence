from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.clients.postgres_client import start_postgres, stop_postgres
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_postgres()
    yield
    await stop_postgres()


app = FastAPI(title="Intelligence Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.service_name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)