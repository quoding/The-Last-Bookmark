from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import card, end, ending, images, sessions, turns
from app.config import get_settings

app = FastAPI(title="마지막 책갈피 API")

_allowed_origins = [o.strip() for o in get_settings().cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(images.router)
app.include_router(turns.router)
app.include_router(card.router)
app.include_router(end.router)
app.include_router(ending.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
