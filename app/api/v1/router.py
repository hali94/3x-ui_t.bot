from fastapi import APIRouter
from app.api.v1 import admin, resellers

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(admin.router)
api_router.include_router(resellers.router)
