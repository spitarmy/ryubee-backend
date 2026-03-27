import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import (
    auth, jobs, admin, customers, manifests, routes,
    invoices, payments, settings, bank, freee, templates, volume
)
# テーブルを自動作成（本番ではAlembicマイグレーション推奨）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Ryu兵衛 API",
    description="立米AI現場見積ツール バックエンドAPI",
    version="1.0.0",
)

# ── CORS（Vercel/GitHub Pagesフロントからのアクセスを許可）────────────
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "https://spitarmy.github.io",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://localhost:5501"
    ],
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


@app.get("/")
def root():
    return {"message": "Ryu兵衛 API is running 🚀", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
