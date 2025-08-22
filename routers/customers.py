from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Customer
from schemas import CustomerCreate, CustomerUpdate, CustomerResponse
from typing import List, Optional
import json

router = APIRouter(prefix="/customers", tags=["Customers"])


# ---------- WebSocket helper ----------
# We keep it async so BackgroundTasks can await it.
async def _ws_broadcast(event: str, payload: dict):
    """
    Broadcasts a JSON message over the shared WebSocket manager.
    Shape: {"type": "<event>", "data": {...}}
    """
    try:
        # NOTE: This imports from your main.py where `manager` lives.
        # If you move manager to notifications.py, change to: from notifications import manager
        from main import manager  # avoids global import at module load time
        message = json.dumps({"type": event, "data": payload}, default=str)
        await manager.broadcast(message)
    except Exception:
        # Don't let WS failures break the API response
        pass


# ---------------- CREATE ----------------
@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer: CustomerCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # case-insensitive email uniqueness
    existing = db.query(Customer).filter(func.lower(Customer.email) == customer.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    db_customer = Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)

    # fire-and-forget WS event
    background_tasks.add_task(
        _ws_broadcast,
        "customer.created",
        {
            "id": db_customer.id,
            "name": db_customer.name,
            "email": db_customer.email,
            "phone": db_customer.phone,
            "created_at": db_customer.created_at,
        },
    )
    return db_customer


# ---------------- READ ALL (with pagination) ----------------
@router.get("/", response_model=List[CustomerResponse])
def get_customers(
    skip: int = 0,
    limit: int = 25,
    db: Session = Depends(get_db),
):
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers


# ---------------- READ ONE ----------------
@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


# ---------------- UPDATE ----------------
@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    updated: CustomerUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = updated.dict(exclude_unset=True)

    # if email changing, enforce conflict (case-insensitive)
    if "email" in update_data and update_data["email"] is not None:
        new_email = update_data["email"]
        existing = (
            db.query(Customer)
            .filter(func.lower(Customer.email) == new_email.lower(), Customer.id != customer_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered with another customer",
            )

    for key, value in update_data.items():
        setattr(customer, key, value)

    db.commit()
    db.refresh(customer)

    background_tasks.add_task(
        _ws_broadcast,
        "customer.updated",
        {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "created_at": customer.created_at,
        },
    )
    return customer


# ---------------- DELETE ----------------
@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.delete(customer)
    db.commit()

    background_tasks.add_task(
        _ws_broadcast,
        "customer.deleted",
        {"id": customer_id},
    )
    return None  # 204 No Content → no response body
