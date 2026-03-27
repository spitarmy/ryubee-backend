"""請求書ルーター: 請求書CRUD・月次一括生成・未入金アラート"""
from datetime import datetime, date
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.database import get_db
from app import models, auth

router = APIRouter(prefix="/v1/invoices", tags=["invoices"])


# ── Schemas ────────────────────────────────────────────
class InvoiceItemCreate(BaseModel):
    description: str = ""
    quantity: float = 1
    unit: str = "式"
    unit_price: float = 0
    amount: int = 0
    manifest_id: str | None = None


class InvoiceCreate(BaseModel):
    customer_id: str
    month: str  # YYYY-MM
    total_amount: int = 0
    tax_amount: int = 0
    status: str = "draft"
    due_date: str | None = None
    notes: str = ""
    items: list[InvoiceItemCreate] = []


class InvoiceUpdate(BaseModel):
    status: str | None = None
    total_amount: int | None = None
    tax_amount: int | None = None
    due_date: str | None = None
    notes: str | None = None
    sent_at: str | None = None


class InvoiceItemOut(BaseModel):
    id: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    amount: int
    manifest_id: str | None
    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    id: str
    amount: int
    payment_date: str
    payment_method: str
    notes: str
    created_at: str
    model_config = {"from_attributes": True}


class InvoiceOut(BaseModel):
    id: str
    company_id: str
    customer_id: str
    customer_name: str = ""
    month: str
    total_amount: int
    tax_amount: int
    status: str
    due_date: str | None
    sent_at: str | None
    notes: str
    freee_synced: bool
    items: list[InvoiceItemOut] = []
    payments: list[PaymentOut] = []
    paid_total: int = 0
    created_at: str
    updated_at: str
    model_config = {"from_attributes": True}


class MonthlyGenerateRequest(BaseModel):
    month: str  # YYYY-MM
    due_date: str | None = None


class UnpaidAlertOut(BaseModel):
    invoice_id: str
    customer_id: str
    customer_name: str
    month: str
    total_amount: int
    paid_total: int
    remaining: int
    due_date: str | None
    is_fiscal_crossover: bool  # 決算跨ぎ売掛金フラグ
    days_overdue: int
    email: str | None = None
    last_reminded_at: str | None = None


# ── Helpers ────────────────────────────────────────────
def _invoice_to_out(inv: models.Invoice) -> InvoiceOut:
    paid = sum(p.amount for p in inv.payments)
    cname = inv.customer.name if inv.customer else ""
    return InvoiceOut(
        id=inv.id,
        company_id=inv.company_id,
        customer_id=inv.customer_id,
        customer_name=cname,
        month=inv.month,
        total_amount=inv.total_amount,
        tax_amount=inv.tax_amount,
        status=inv.status,
        due_date=inv.due_date,
        sent_at=inv.sent_at,
        notes=inv.notes,
        freee_synced=inv.freee_synced,
        items=[InvoiceItemOut(
            id=it.id, description=it.description, quantity=it.quantity,
            unit=it.unit, unit_price=it.unit_price, amount=it.amount,
            manifest_id=it.manifest_id,
        ) for it in inv.items],
        payments=[PaymentOut(
            id=p.id, amount=p.amount, payment_date=p.payment_date,
            payment_method=p.payment_method, notes=p.notes,
            created_at=p.created_at.isoformat(),
        ) for p in inv.payments],
        paid_total=paid,
        created_at=inv.created_at.isoformat(),
        updated_at=inv.updated_at.isoformat(),
    )


# ── Endpoints ──────────────────────────────────────────
@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    month: str | None = Query(None),
    status: str | None = Query(None),
    customer_id: str | None = Query(None),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Invoice).options(
        joinedload(models.Invoice.items),
        joinedload(models.Invoice.payments),
        joinedload(models.Invoice.customer),
    ).filter_by(company_id=current_user.company_id)
    if month:
        q = q.filter(models.Invoice.month == month)
    if status:
        q = q.filter(models.Invoice.status == status)
    if customer_id:
        q = q.filter(models.Invoice.customer_id == customer_id)
    invoices = q.order_by(models.Invoice.month.desc(), models.Invoice.created_at.desc()).all()
    # deduplicate due to joinedload
    seen = set()
    unique = []
    for inv in invoices:
        if inv.id not in seen:
            seen.add(inv.id)
            unique.append(inv)
    return [_invoice_to_out(i) for i in unique]


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(
    body: InvoiceCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    cust = db.query(models.Customer).filter_by(
        id=body.customer_id, company_id=current_user.company_id
    ).first()
    if not cust:
        raise HTTPException(404, "顧客が見つかりません")

    inv = models.Invoice(
        company_id=current_user.company_id,
        customer_id=body.customer_id,
        month=body.month,
        total_amount=body.total_amount,
        tax_amount=body.tax_amount,
        status=body.status,
        due_date=body.due_date,
        notes=body.notes,
    )
    db.add(inv)
    db.flush()

    for item in body.items:
        db.add(models.InvoiceItem(
            invoice_id=inv.id,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            amount=item.amount,
            manifest_id=item.manifest_id,
        ))

    db.commit()
    db.refresh(inv)
    inv = db.query(models.Invoice).options(
        joinedload(models.Invoice.items),
        joinedload(models.Invoice.payments),
        joinedload(models.Invoice.customer),
    ).filter_by(id=inv.id).first()
    return _invoice_to_out(inv)


@router.get("/unpaid-alerts", response_model=list[UnpaidAlertOut])
def unpaid_alerts(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """未入金アラート: 業者別締め払い日を考慮して未払い請求書を返す"""
    settings = db.query(models.CompanySettings).filter_by(
        company_id=current_user.company_id
    ).first()
    fiscal_end_month = settings.fiscal_year_end_month if settings else 3

    invoices = db.query(models.Invoice).options(
        joinedload(models.Invoice.payments),
        joinedload(models.Invoice.customer),
    ).filter(
        models.Invoice.company_id == current_user.company_id,
        models.Invoice.status.in_(["sent", "partial", "overdue", "draft"]),
    ).all()

    seen = set()
    unique = []
    for inv in invoices:
        if inv.id not in seen:
            seen.add(inv.id)
            unique.append(inv)

    today = date.today()
    alerts = []
    for inv in unique:
        paid = sum(p.amount for p in inv.payments)
        remaining = inv.total_amount - paid
        if remaining <= 0:
            continue

        # 業者別の支払期限を算出
        customer_due = _calc_customer_due_date(inv, inv.customer)

        # 支払期限前の請求書はアラート対象外
        if customer_due and today <= customer_due:
            continue

        days_overdue = 0
        if customer_due:
            days_overdue = (today - customer_due).days

        is_crossover = False
        try:
            inv_year, inv_month = int(inv.month[:4]), int(inv.month[5:7])
            if fiscal_end_month >= inv_month:
                fiscal_year_end = date(inv_year, fiscal_end_month, 28)
            else:
                fiscal_year_end = date(inv_year + 1, fiscal_end_month, 28)
            if today > fiscal_year_end:
                is_crossover = True
        except (ValueError, IndexError):
            pass

        cname = inv.customer.name if inv.customer else ""
        cemail = inv.customer.email if inv.customer else None
        alerts.append(UnpaidAlertOut(
            invoice_id=inv.id,
            customer_id=inv.customer_id,
            customer_name=cname,
            month=inv.month,
            total_amount=inv.total_amount,
            paid_total=paid,
            remaining=remaining,
            due_date=customer_due.isoformat() if customer_due else inv.due_date,
            is_fiscal_crossover=is_crossover,
            days_overdue=days_overdue,
            email=cemail,
            last_reminded_at=inv.last_reminded_at,
        ))

    alerts.sort(key=lambda a: (-int(a.is_fiscal_crossover), -a.days_overdue))
    return alerts


def _calc_customer_due_date(inv: models.Invoice, customer) -> date | None:
    """業者の締め払い設定に基づいて支払期限を計算"""
    if not customer:
        if inv.due_date:
            try:
                return datetime.strptime(inv.due_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        return None

    try:
        inv_year, inv_month = int(inv.month[:4]), int(inv.month[5:7])
    except (ValueError, IndexError):
        return None

    offset = getattr(customer, 'payment_due_month_offset', 1) or 1
    due_day = getattr(customer, 'payment_due_day', 31) or 31

    pay_month = inv_month + offset
    pay_year = inv_year
    while pay_month > 12:
        pay_month -= 12
        pay_year += 1

    import calendar
    last_day = calendar.monthrange(pay_year, pay_month)[1]
    actual_due_day = min(due_day, last_day)

    return date(pay_year, pay_month, actual_due_day)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    inv = db.query(models.Invoice).options(
        joinedload(models.Invoice.items),
        joinedload(models.Invoice.payments),
        joinedload(models.Invoice.customer),
    ).filter_by(id=invoice_id, company_id=current_user.company_id).first()
    if not inv:
        raise HTTPException(404, "請求書が見つかりません")
    return _invoice_to_out(inv)


@router.put("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: str,
    body: InvoiceUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    inv = db.query(models.Invoice).filter_by(
        id=invoice_id, company_id=current_user.company_id
    ).first()
    if not inv:
        raise HTTPException(404, "請求書が見つかりません")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(inv, field, val)
    db.commit()
    db.refresh(inv)
    inv = db.query(models.Invoice).options(
        joinedload(models.Invoice.items),
        joinedload(models.Invoice.payments),
        joinedload(models.Invoice.customer),
    ).filter_by(id=inv.id).first()
    return _invoice_to_out(inv)


@router.post("/generate-monthly", response_model=list[InvoiceOut])
def generate_monthly_invoices(
    body: MonthlyGenerateRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """指定月の産廃マニフェスト（重量課金）に基づいて請求書を一括生成"""
    company_id = current_user.company_id
    month = body.month  # YYYY-MM

    # この月に発行された産廃マニフェストを取得
    customers = db.query(models.Customer).filter_by(company_id=company_id).all()
    c_ids = [c.id for c in customers]
    c_map = {c.id: c for c in customers}
    if not c_ids:
        return []

    manifests = db.query(models.Manifest).filter(
        models.Manifest.customer_id.in_(c_ids),
        models.Manifest.issue_date.like(f"{month}%"),
    ).all()

    # 顧客ごとにグルーピング
    from collections import defaultdict
    cust_manifests: dict[str, list[models.Manifest]] = defaultdict(list)
    for m in manifests:
        cust_manifests[m.customer_id].append(m)

    created = []
    for cust_id, ms in cust_manifests.items():
        # 既存請求書チェック（重複防止）
        existing = db.query(models.Invoice).filter_by(
            company_id=company_id, customer_id=cust_id, month=month
        ).first()
        if existing:
            continue

        items = []
        total = 0
        for m in ms:
            if m.weight_kg and m.unit_price_per_kg:
                amt = int(m.weight_kg * m.unit_price_per_kg)
            else:
                amt = 0
            items.append(models.InvoiceItem(
                description=f"産廃処理: {m.waste_type or '廃棄物'} ({m.weight_kg or 0}kg)",
                quantity=m.weight_kg or 0,
                unit="kg",
                unit_price=m.unit_price_per_kg or 0,
                amount=amt,
                manifest_id=m.id,
            ))
            total += amt

        tax = int(total * 0.1)
        inv = models.Invoice(
            company_id=company_id,
            customer_id=cust_id,
            month=month,
            total_amount=total + tax,
            tax_amount=tax,
            status="draft",
            due_date=body.due_date or _auto_due_date(customer, month),
        )
        db.add(inv)
        db.flush()

        for item in items:
            item.invoice_id = inv.id
            db.add(item)

        created.append(inv)

    db.commit()

    result = []
    for inv in created:
        loaded = db.query(models.Invoice).options(
            joinedload(models.Invoice.items),
            joinedload(models.Invoice.payments),
            joinedload(models.Invoice.customer),
        ).filter_by(id=inv.id).first()
        result.append(_invoice_to_out(loaded))

    return result


def _auto_due_date(customer, month: str) -> str | None:
    """業者の締め払い設定に基づいて支払期限日文字列を自動生成"""
    if not customer:
        return None
    import calendar
    try:
        inv_year, inv_month = int(month[:4]), int(month[5:7])
    except (ValueError, IndexError):
        return None
    offset = getattr(customer, 'payment_due_month_offset', 1) or 1
    due_day = getattr(customer, 'payment_due_day', 31) or 31
    pay_month = inv_month + offset
    pay_year = inv_year
    while pay_month > 12:
        pay_month -= 12
        pay_year += 1
    last_day = calendar.monthrange(pay_year, pay_month)[1]
    actual_due_day = min(due_day, last_day)
    return f"{pay_year}-{pay_month:02d}-{actual_due_day:02d}"


# ── 見積→請求書変換 ──────────────────────────────────────
@router.post("/from-estimate/{job_id}", response_model=InvoiceOut, status_code=201)
def create_invoice_from_estimate(
    job_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """見積（案件）から直接請求書を生成。価格決まってる見積書はそのまま請求にする。"""
    job = db.query(models.Job).filter_by(
        job_id=job_id, company_id=current_user.company_id
    ).first()
    if not job:
        raise HTTPException(404, "案件が見つかりません")

    amount = job.final_price or job.estimated_price or job.price_total or 0
    if amount <= 0:
        raise HTTPException(400, "金額が0円です。見積金額を設定してください。")

    customer_id = job.customer_id
    if not customer_id:
        raise HTTPException(400, "案件に顧客が紐づいていません")

    customer = db.query(models.Customer).filter_by(id=customer_id).first()
    now = date.today()
    month = f"{now.year}-{now.month:02d}"

    due_date_str = _auto_due_date(customer, month)

    tax = int(amount * 0.1)
    inv = models.Invoice(
        company_id=current_user.company_id,
        customer_id=customer_id,
        month=month,
        total_amount=amount + tax,
        tax_amount=tax,
        status="draft",
        due_date=due_date_str,
        notes=f"案件「{job.job_name}」より変換",
    )
    db.add(inv)
    db.flush()

    db.add(models.InvoiceItem(
        invoice_id=inv.id,
        description=job.job_name or "業務委託",
        quantity=1,
        unit="式",
        unit_price=amount,
        amount=amount,
    ))

    if job.discount_amount and job.discount_amount > 0:
        db.add(models.InvoiceItem(
            invoice_id=inv.id,
            description="値引き",
            quantity=1,
            unit="式",
            unit_price=-job.discount_amount,
            amount=-job.discount_amount,
        ))

    if job.surcharge_amount and job.surcharge_amount > 0:
        db.add(models.InvoiceItem(
            invoice_id=inv.id,
            description="追加料金",
            quantity=1,
            unit="式",
            unit_price=job.surcharge_amount,
            amount=job.surcharge_amount,
        ))

    db.commit()
    db.refresh(inv)
    inv = db.query(models.Invoice).options(
        joinedload(models.Invoice.items),
        joinedload(models.Invoice.payments),
        joinedload(models.Invoice.customer),
    ).filter_by(id=inv.id).first()
    return _invoice_to_out(inv)


# ── 現場現金回収 (見積→請求→入金完了) ────────────────────────
@router.post("/cash-collection/{job_id}", response_model=InvoiceOut, status_code=201)
def record_cash_collection(
    job_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """現場での現金回収: 見積から請求書を作り、即座に全額の現金入金履歴をつける"""
    job = db.query(models.Job).filter_by(
        job_id=job_id, company_id=current_user.company_id
    ).first()
    if not job:
        raise HTTPException(404, "案件が見つかりません")

    amount = job.final_price or job.estimated_price or job.price_total or 0
    if amount <= 0:
        raise HTTPException(400, "金額が0円です。見積金額を設定してください。")

    customer_id = job.customer_id
    if not customer_id:
        raise HTTPException(400, "案件に顧客が紐づいていません")

    customer = db.query(models.Customer).filter_by(id=customer_id).first()
    now = date.today()
    month = f"{now.year}-{now.month:02d}"
    due_date_str = _auto_due_date(customer, month)

    tax = int(amount * 0.1)
    total_with_tax = amount + tax

    inv = models.Invoice(
        company_id=current_user.company_id,
        customer_id=customer_id,
        month=month,
        total_amount=total_with_tax,
        tax_amount=tax,
        status="paid",  # 現金回収なのですぐにpaid
        due_date=due_date_str,
        notes=f"案件「{job.job_name}」より変換 (現場現金回収)",
    )
    db.add(inv)
    db.flush()

    db.add(models.InvoiceItem(
        invoice_id=inv.id,
        description=job.job_name or "業務委託",
        quantity=1,
        unit="式",
        unit_price=amount,
        amount=amount,
    ))

    if job.discount_amount and job.discount_amount > 0:
        db.add(models.InvoiceItem(
            invoice_id=inv.id,
            description="値引き",
            quantity=1,
            unit="式",
            unit_price=-job.discount_amount,
            amount=-job.discount_amount,
        ))

    if job.surcharge_amount and job.surcharge_amount > 0:
        db.add(models.InvoiceItem(
            invoice_id=inv.id,
            description="追加料金",
            quantity=1,
            unit="式",
            unit_price=job.surcharge_amount,
            amount=job.surcharge_amount,
        ))

    db.flush()

    # 現金入金履歴の追加
    db.add(models.Payment(
        invoice_id=inv.id,
        company_id=current_user.company_id,
        amount=total_with_tax,
        payment_date=now.isoformat(),
        payment_method="cash",
        notes="現場現金回収"
    ))

    # 案件のステータスを自動更新（任意）
    job.stage = "completed"

    db.commit()
    db.refresh(inv)
    inv = db.query(models.Invoice).options(
        joinedload(models.Invoice.items),
        joinedload(models.Invoice.payments),
        joinedload(models.Invoice.customer),
    ).filter_by(id=inv.id).first()
    return _invoice_to_out(inv)


class SendRemindersResponse(BaseModel):
    sent_count: int
    logs: list[str]

@router.post("/send-reminders", response_model=SendRemindersResponse)
def send_reminders(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    未入金アラートが出ている顧客（かつメールアドレスがある）に一斉にリマインドを送信する。
    ※今回は実際のSMTP送信ではなく、ログに出力して last_reminded_at を更新する。
    """
    # 1. 会社設定（テンプレート）を取得
    settings = db.query(models.CompanySettings).filter_by(
        company_id=current_user.company_id
    ).first()
    
    subject_tmpl = settings.unpaid_email_subject if settings else "【重要】未入金のお知らせ"
    body_tmpl = settings.unpaid_email_body if settings else "未入金のお知らせ\n\n{{customer_name}}様\n請求月: {{month}}\n金額: ¥{{amount}}\n期限: {{due_date}}"

    # 2. 未入金アラートリストを取得（再利用）
    alerts = unpaid_alerts(current_user=current_user, db=db)
    
    sent_count = 0
    logs = []
    now_str = datetime.now().isoformat()

    for alert in alerts:
        if not alert.email:
            continue
            
        # Invoice取得して最新状態確認
        inv = db.query(models.Invoice).filter_by(id=alert.invoice_id).first()
        if not inv:
            continue
            
        # 生成
        body = body_tmpl.replace("{{customer_name}}", alert.customer_name)
        body = body.replace("{{month}}", alert.month)
        body = body.replace("{{amount}}", f"{alert.remaining:,}")
        due_str = alert.due_date or "指定なし"
        body = body.replace("{{due_date}}", due_str)
        
        # 本来ならここで send_email(to=alert.email, subject=subject_tmpl, body=body) を実行する
        logs.append(f"Sent to {alert.email} ({alert.customer_name}): ¥{alert.remaining:,}")
        
        # 記録更新
        inv.last_reminded_at = now_str
        sent_count += 1

    db.commit()
    return SendRemindersResponse(sent_count=sent_count, logs=logs)
