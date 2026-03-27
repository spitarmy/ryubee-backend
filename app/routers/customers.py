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
            id=obj.id,
            company_id=obj.company_id,
            name=obj.name,
            address=obj.address,
            phone=obj.phone,
            contract_type=obj.contract_type,
            email=obj.email,
            contact_person=obj.contact_person,
            notes=obj.notes,
            contract_expiry_date=obj.contract_expiry_date,
            billing_closing_day=obj.billing_closing_day,
            payment_due_month_offset=obj.payment_due_month_offset,
            payment_due_day=obj.payment_due_day,
            form_data=obj.form_data or "{}",
            created_at=obj.created_at.isoformat()
        )


@router.get("", response_model=list[CustomerOut])
def list_customers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    customers = db.query(models.Customer).filter_by(
        company_id=current_user.company_id
    ).order_by(models.Customer.created_at.desc()).all()
    return [CustomerOut.from_orm_obj(c) for c in customers]


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
