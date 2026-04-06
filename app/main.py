import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.routers import (
    auth, jobs, admin, customers, manifests, routes,
    invoices, payments, settings, bank, freee, templates, volume, daily_reports
)
# テーブルを自動作成（本番ではAlembicマイグレーション推奨）
Base.metadata.create_all(bind=engine)

# 起動時の自動マイグレーション（新カラム追加）
try:
    with engine.connect() as _conn:
        _conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS company_logo TEXT DEFAULT ''"
        ))
        _conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS company_stamp TEXT DEFAULT ''"
        ))
        _conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS general_waste_pricing TEXT DEFAULT '{}'"
        ))
        _conn.commit()
except Exception as _e:
    print(f"Auto-migration skipped: {_e}")

app = FastAPI(
    title="Ryu兵衛 API",
    description="立米AI現場見積ツール バックエンドAPI",
    version="1.0.0",
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ── CORS（Vercel/GitHub Pagesフロントからのアクセスを許可）────────────
env_origin = os.getenv("FRONTEND_ORIGIN", "")
allowed_origins = [
    "https://spitarmy.github.io",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://localhost:5501"
]
if env_origin and env_origin != "*":
    allowed_origins.append(env_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ルーターを登録 ──────────────────────────────────────
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(jobs.router)
app.include_router(admin.router)
app.include_router(customers.router)
app.include_router(manifests.router)
app.include_router(routes.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(bank.router)
app.include_router(freee.router)
app.include_router(templates.router)
app.include_router(volume.router)
app.include_router(daily_reports.router)


@app.get("/")
def root():
    return {"message": "Ryu兵衛 API is running 🚀", "docs": "/docs"}

from sqlalchemy.orm import Session
from app.database import get_db, engine
from sqlalchemy import text

@app.get("/health")
def health():
    return {"status": "ok"}
