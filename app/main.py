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


@app.get("/")
def root():
    return {"message": "Ryu兵衛 API is running 🚀", "docs": "/docs"}

from sqlalchemy.orm import Session
from app.database import get_db, engine
from sqlalchemy import text

@app.get("/v1/debug_seed")
def debug_seed():
    try:
        from app.database import SessionLocal
        import uuid
        import json
        from datetime import datetime, date
        from app import models
        db = SessionLocal()
        try:
            user = db.query(models.User).filter_by(email="test@yamabun.com").first()
            if not user:
                return {"error": "test@yamabun.com not found"}
            company_id = user.company_id
            
            existing = db.query(models.Customer).filter_by(company_id=company_id).count()
            if existing > 0:
                return {"status": f"Already seeded: {existing} customers exist"}

            now_iso = datetime.now().isoformat()
            customers = [
                models.Customer(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    name="京都テスト株式会社",
                    address="京都府京都市中京区1-1-1",
                    phone="075-111-2222",
                    contract_type="subscription",
                    email="kyoto-test@example.com",
                    contact_person="山田 太郎",
                    notes="ダンボール回収（週2回）",
                    form_data=json.dumps({
                        "corporate_number": "1234567890123",
                        "representative_name": "京都 太郎",
                        "representative_title": "代表取締役",
                        "business_type": "飲食業",
                        "contract_date": "2024-04-01",
                        "contract_amount": "50000",
                        "collection_items": ["燃えるゴミ", "ダンボール"]
                    }),
                    created_at=datetime.now()
                ),
                models.Customer(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    name="株式会社 京都和風リゾート",
                    address="京都府京都市下京区2-2-2",
                    phone="075-333-4444",
                    contract_type="spot",
                    email="resort@example.com",
                    contact_person="佐藤 花子",
                    notes="粗大ごみ回収（スポット）",
                    form_data=json.dumps({
                        "corporate_number": "9876543210987",
                        "representative_name": "佐藤 一郎",
                        "representative_title": "取締役社長",
                        "business_type": "宿泊業",
                        "contract_date": "2024-05-15",
                        "contract_amount": "120000",
                        "collection_items": ["粗大ゴミ", "産業廃棄物"]
                    }),
                    created_at=datetime.now()
                ),
                models.Customer(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    name="高辻グリーンマンション 管理組合",
                    address="京都府京都市左京区3-3-3",
                    phone="075-555-6666",
                    contract_type="subscription",
                    email="green@example.com",
                    contact_person="鈴木 一郎",
                    notes="一般ごみ回収（週3回）",
                    form_data=json.dumps({
                        "corporate_number": "0000000000000",
                        "representative_name": "鈴木 組合長",
                        "representative_title": "管理組合長",
                        "business_type": "不動産管理",
                        "contract_date": "2023-11-01",
                        "contract_amount": "30000",
                        "collection_items": ["燃えるゴミ", "不燃ゴミ"]
                    }),
                    created_at=datetime.now()
                )
            ]
            
            for c in customers:
                db.add(c)
            db.commit()
            return {"status": "Seeded 3 sample customers!"}
        finally:
            db.close()
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


@app.get("/health")
def health():
    return {"status": "ok"}
