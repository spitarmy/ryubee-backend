import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="company")
    settings: Mapped["CompanySettings"] = relationship(back_populates="company", uselist=False)
    jobs: Mapped[list["Job"]] = relationship(back_populates="company")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String, ForeignKey("companies.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="staff")  # admin / staff
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped["Company"] = relationship(back_populates="users")
    jobs: Mapped[list["Job"]] = relationship(back_populates="user")


class CompanySettings(Base):
    __tablename__ = "company_settings"

    company_id: Mapped[str] = mapped_column(String, ForeignKey("companies.id"), primary_key=True)
    # 会社情報
    company_address: Mapped[str] = mapped_column(Text, default="")
    company_phone: Mapped[str] = mapped_column(String(100), default="")
    company_invoice_no: Mapped[str] = mapped_column(String(100), default="")
    company_bank_info: Mapped[str] = mapped_column(Text, default="")
    # 基本料金
    base_price_m3: Mapped[int] = mapped_column(Integer, default=15000)
    # 搬出オプション
    stairs_2f_price: Mapped[int] = mapped_column(Integer, default=2000)
    stairs_3f_price: Mapped[int] = mapped_column(Integer, default=4000)
    far_parking_price: Mapped[int] = mapped_column(Integer, default=3000)
    # リサイクル4品目
    recycle_tv: Mapped[int] = mapped_column(Integer, default=3000)
    recycle_fridge: Mapped[int] = mapped_column(Integer, default=5000)
    recycle_washer: Mapped[int] = mapped_column(Integer, default=4000)
    recycle_ac: Mapped[int] = mapped_column(Integer, default=3500)
    # マットレス（サイズ別）
    mattress_single: Mapped[int] = mapped_column(Integer, default=3000)
    mattress_semi_double: Mapped[int] = mapped_column(Integer, default=4000)
    mattress_double: Mapped[int] = mapped_column(Integer, default=5000)
    mattress_queen_king: Mapped[int] = mapped_column(Integer, default=7000)
    # ソファー（人掛け別）
    sofa_1p: Mapped[int] = mapped_column(Integer, default=2000)
    sofa_2p: Mapped[int] = mapped_column(Integer, default=3500)
    sofa_3p: Mapped[int] = mapped_column(Integer, default=5000)
    sofa_large: Mapped[int] = mapped_column(Integer, default=8000)
    # その他特例品
    safe_price: Mapped[int] = mapped_column(Integer, default=15000)
    piano_price: Mapped[int] = mapped_column(Integer, default=20000)
    bike_price: Mapped[int] = mapped_column(Integer, default=5000)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    company: Mapped["Company"] = relationship(back_populates="settings")


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String, ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    # 案件情報
    job_name: Mapped[str] = mapped_column(String(500), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    work_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    # AI算出結果
    total_volume_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_result: Mapped[str] = mapped_column(Text, default="")  # JSON文字列
    # 料金・状態
    price_total: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending/confirmed/completed
    # 電子署名
    signature_data: Mapped[str] = mapped_column(Text, default="")  # Base64
    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    company: Mapped["Company"] = relationship(back_populates="jobs")
    user: Mapped["User | None"] = relationship(back_populates="jobs")
