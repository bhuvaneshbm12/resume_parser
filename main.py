from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import close_db, connect_db, init_db
from routers.parse import router as parse_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Resume Parser API", lifespan=lifespan)
app.include_router(parse_router)
