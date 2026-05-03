from fastapi import APIRouter
from app.services.repo_service import clone_repo

router = APIRouter(prefix="/repos", tags=["repos"])

@router.post("/upload")
def upload_repo(repo_url: str):
    path = clone_repo(repo_url)
    return {"message": f"Repository cloned to {path}"}