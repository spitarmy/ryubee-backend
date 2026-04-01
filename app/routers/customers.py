from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, auth

router = APIRouter(prefix="/v1/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    name: str
    address: str = ""
    phone: str = ""
    contract_type: str = "spot"
    email: str = ""
    contact_person: str = ""
    notes: str = ""
    contract_expiry_date: str | None = None
    billing_closing_day: int = 31
    payment_due_month_offset: int = 1
    payment_due_day: int = 31
    form_data: str = "{}"


class CustomerHistoryCreate(BaseModel):
    event_type: str = "note"
    description: str


class CustomerHistoryOut(BaseModel):
    id: str
    customer_id: str
    event_type: str
    description: str
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, obj: models.CustomerHistory):
        return cls(
            id=str(obj.id),
            customer_id=str(obj.customer_id),
            event_type=str(obj.event_type),
            description=str(obj.description),
            created_at=obj.created_at.isoformat() if obj.created_at else ""
        )


class CustomerUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    contract_type: str | None = None
    email: str | None = None
    contact_person: str | None = None
    notes: str | None = None
    contract_expiry_date: str | None = None
    billing_closing_day: int | None = None
    payment_due_month_offset: int | None = None
    payment_due_day: int | None = None
    form_data: str | None = None


class CustomerOut(BaseModel):
    id: str
    company_id: str
    name: str
    address: str
    phone: str
    contract_type: str
    email: str
    contact_person: str
    notes: str
    contract_expiry_date: str | None
    billing_closing_day: int = 31
    payment_due_month_offset: int = 1
    payment_due_day: int = 31
    form_data: str = "{}"
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, obj: models.Customer):
        return cls(
            id=str(obj.id) if obj.id else "",
            company_id=str(obj.company_id) if obj.company_id else "",
            name=str(obj.name) if obj.name else "名称未設定",
            address=str(obj.address) if obj.address else "",
            phone=str(obj.phone) if obj.phone else "",
            contract_type=str(obj.contract_type) if obj.contract_type else "spot",
            email=str(obj.email) if obj.email else "",
            contact_person=str(obj.contact_person) if obj.contact_person else "",
            notes=str(obj.notes) if obj.notes else "",
            contract_expiry_date=str(obj.contract_expiry_date) if obj.contract_expiry_date else None,
            billing_closing_day=int(obj.billing_closing_day) if obj.billing_closing_day is not None else 31,
            payment_due_month_offset=int(obj.payment_due_month_offset) if obj.payment_due_month_offset is not None else 1,
            payment_due_day=int(obj.payment_due_day) if obj.payment_due_day is not None else 31,
            form_data=str(obj.form_data) if obj.form_data else "{}",
            created_at=obj.created_at.isoformat() if obj.created_at else ""
        )


@router.get("")
def list_customers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        customers = db.query(models.Customer).filter_by(
            company_id=current_user.company_id
        ).order_by(models.Customer.created_at.desc()).all()
        return [CustomerOut.from_orm_obj(c).model_dump() for c in customers]
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        # Raise 400 instead of 500 so CORS headers are not dropped by FastAPI!
        raise HTTPException(status_code=400, detail=f"DEBUG ERROR: {str(e)}\n\n{error_info}")


@router.post("", response_model=CustomerOut)
def create_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    new_cust = models.Customer(
        company_id=current_user.company_id,
        name=body.name,
        address=body.address,
        phone=body.phone,
        contract_type=body.contract_type,
        email=body.email,
        contact_person=body.contact_person,
        notes=body.notes,
        contract_expiry_date=body.contract_expiry_date,
        billing_closing_day=body.billing_closing_day,
        payment_due_month_offset=body.payment_due_month_offset,
        payment_due_day=body.payment_due_day,
        form_data=body.form_data,
    )
    db.add(new_cust)
    db.commit()
    db.refresh(new_cust)
    return CustomerOut.from_orm_obj(new_cust)


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    cust = db.query(models.Customer).filter_by(
        id=customer_id, company_id=current_user.company_id
    ).first()
    if not cust:
        raise HTTPException(404, "顧客が見つかりません")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(cust, field, val)
    db.commit()
    db.refresh(cust)
    return CustomerOut.from_orm_obj(cust)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: str,
    current_user: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    cust = db.query(models.Customer).filter_by(
        id=customer_id, company_id=current_user.company_id
    ).first()
    if not cust:
        raise HTTPException(404, "顧客が見つかりません")
    db.delete(cust)
    db.commit()


@router.get("/{customer_id}/history")
def list_customer_history(
    customer_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    cust = db.query(models.Customer).filter_by(
        id=customer_id, company_id=current_user.company_id
    ).first()
    if not cust:
        raise HTTPException(404, "顧客が見つかりません")
    
    return [CustomerHistoryOut.from_orm_obj(h).model_dump() for h in cust.history_logs]


@router.post("/{customer_id}/history", response_model=CustomerHistoryOut)
def add_customer_history(
    customer_id: str,
    body: CustomerHistoryCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    cust = db.query(models.Customer).filter_by(
        id=customer_id, company_id=current_user.company_id
    ).first()
    if not cust:
        raise HTTPException(404, "顧客が見つかりません")
    
    new_log = models.CustomerHistory(
        customer_id=customer_id,
        event_type=body.event_type,
        description=body.description
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return CustomerHistoryOut.from_orm_obj(new_log)
