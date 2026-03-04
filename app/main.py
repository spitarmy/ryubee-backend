import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, settings, jobs, admin

# テーブルを自動作成（本番ではAlembicマイグレーション推奨）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Ryu兵衛 API",
    description="立米AI現場見積ツール バックエンドAPI",
    version="1.0.0",
)

# ── CORS（Vercelフロントからのアクセスを許可）────────────
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ルーターを登録 ──────────────────────────────────────
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(jobs.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"message": "Ryu兵衛 API is running 🚀", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
