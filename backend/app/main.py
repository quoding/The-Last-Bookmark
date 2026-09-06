from fastapi import FastAPI

from app.api import images, sessions

app = FastAPI(title="마지막 책갈피 API")

app.include_router(sessions.router)
app.include_router(images.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
