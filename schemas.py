from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ---------------- ENUMS ----------------
class TicketStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    assigned = "assigned"
    pending_customer = "pending_customer"
    closed = "closed"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ---------------- CUSTOMERS ----------------
class CustomerBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------- AGENTS ----------------
class AgentBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class AgentResponse(AgentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------- PRODUCTS ----------------
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float  # ✅ safer than Decimal for JSON serialization
    priority: Priority = Priority.low


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    priority: Optional[Priority] = None


class ProductResponse(ProductBase):
    id: int

    class Config:
        from_attributes = True


# ---------------- TICKETS ----------------
class TicketBase(BaseModel):
    title: str
    description: str
    priority: Priority = Priority.low
    product_id: int


class TicketCreate(TicketBase):
    customer_id: int
    agent_id: Optional[int] = None  # auto-assign if not provided


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[TicketStatus] = None
    agent_id: Optional[int] = None
    product_id: Optional[int] = None


class TicketResponse(BaseModel):
    id: int
    title: str
    description: str
    priority: Priority
    status: TicketStatus
    customer_id: int
    agent_id: Optional[int] = None
    product_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    # Optional expansions for frontend convenience
    customer: Optional[CustomerResponse] = None
    agent: Optional[AgentResponse] = None
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


# ---------------- WEBSOCKET MESSAGE ----------------
class WSMessage(BaseModel):
    event: str  # e.g., "ticket_created", "ticket_updated", "ticket_closed"
    data: Dict[str, Any]
