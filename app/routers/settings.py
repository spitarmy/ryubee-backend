"""設定ルーター: 料金マスタ + 会社情報の取得・保存"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, auth

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class SettingsSchema(BaseModel):
    # 会社情報
    company_name: str = ""
    company_address: str = ""
    company_phone: str = ""
    company_invoice_no: str = ""
    company_bank_info: str = ""
    # 基本料金
    base_price_m3: int = 15000
    # 搬出オプション
    stairs_2f_price: int = 2000
    stairs_3f_price: int = 4000
    far_parking_price: int = 3000
    # リサイクル4品目
    recycle_tv: int = 3000
    recycle_fridge: int = 5000
    recycle_washer: int = 4000
    recycle_ac: int = 3500
    # マットレス
    mattress_single: int = 3000
    mattress_semi_double: int = 4000
    mattress_double: int = 5000
    mattress_queen_king: int = 7000
    # ソファー
    sofa_1p: int = 2000
    sofa_2p: int = 3500
    sofa_3p: int = 5000
    sofa_large: int = 8000
    # その他
    safe_price: int = 15000
    piano_price: int = 20000
    bike_price: int = 5000

    model_config = {"from_attributes": True}


@router.get("", response_model=SettingsSchema)
def get_settings(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """自社の料金設定を取得（全ロールが取得可能）"""
    rec = db.get(models.CompanySettings, current_user.company_id)
    if not rec:
        # CompanySettings が無ければデフォルト値で自動生成
        rec = models.CompanySettings(company_id=current_user.company_id)
        db.add(rec)
        db.commit()
        db.refresh(rec)

    # company_name は Company テーブルから
    data = SettingsSchema.model_validate(rec)
    data.company_name = rec.company.name
    return data


@router.put("", response_model=SettingsSchema)
def update_settings(
    body: SettingsSchema,
    current_user: models.User = Depends(auth.require_admin),  # 管理者のみ変更可
    db: Session = Depends(get_db),
):
    """設定を保存（管理者のみ）"""
    rec = db.get(models.CompanySettings, current_user.company_id)
    if not rec:
        rec = models.CompanySettings(company_id=current_user.company_id)
        db.add(rec)

    # 会社名は Company テーブルを更新
    if body.company_name:
        rec.company.name = body.company_name

    # CompanySettings フィールドを一括更新
    exclude = {"company_name"}
    for field, val in body.model_dump(exclude=exclude).items():
        if hasattr(rec, field):
            setattr(rec, field, val)

    db.commit()
    db.refresh(rec)

    result = SettingsSchema.model_validate(rec)
    result.company_name = rec.company.name
    return result
