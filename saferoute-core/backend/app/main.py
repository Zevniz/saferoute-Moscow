from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# Настройка CORS для работы с React фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В продакшене заменить на домен фронтенда
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "SafeRoute Engine V2 Active"}
