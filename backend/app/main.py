from fastapi import FastAPI

from app.api import card, end, ending, images, sessions, turns

app = FastAPI(title="마지막 책갈피 API")

app.include_router(sessions.router)
app.include_router(images.router)
app.include_router(turns.router)
app.include_router(card.router)
app.include_router(end.router)
app.include_router(ending.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
