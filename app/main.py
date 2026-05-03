from fastapi import FastAPI
from app.routes.repo_routes import router as repo_router

app = FastAPI()
app.include_router(repo_router)