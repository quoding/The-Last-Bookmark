import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.models import Image

router = APIRouter(prefix="/api")


@router.get("/images/{image_id}")
def get_image(image_id: str, db: DbSession = Depends(get_db)):
    try:
        iid = uuid.UUID(image_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
    image = db.get(Image, iid)
    if image is None:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
    path = Path(image.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="이미지 파일을 찾을 수 없습니다.")
    return FileResponse(path, media_type="image/webp")
