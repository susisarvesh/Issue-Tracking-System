from sqlalchemy import Column, Integer, String, Text, Enum, ForeignKey, TIMESTAMP, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


# ---------------- ENUMS ----------------
class TicketStatus(enum.Enum):
    open = "open"
    in_progress = "in_progress"
    assigned = "assigned"
    pending_customer = "pending_customer"
    closed = "closed"


class Priority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ---------------- CUSTOMERS ----------------
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20))
    created_at = Column(TIMESTAMP, server_default=func.now())

    tickets = relationship("Ticket", back_populates="customer", cascade="all, delete-orphan")


# ---------------- AGENTS ----------------
class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20))
    created_at = Column(TIMESTAMP, server_default=func.now())

    # ❌ no delete-orphan, otherwise deleting agent wipes tickets
    tickets = relationship("Ticket", back_populates="agent")


# ---------------- PRODUCTS ----------------
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    priority = Column(Enum(Priority, native_enum=False), default=Priority.low)

    tickets = relationship("Ticket", back_populates="product", cascade="all, delete-orphan")


# ---------------- TICKETS ----------------
class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    priority = Column(Enum(Priority, native_enum=False), default=Priority.low)
    status = Column(Enum(TicketStatus, native_enum=False), default=TicketStatus.open)

    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    closed_at = Column(TIMESTAMP)

    # Relationships
    customer = relationship("Customer", back_populates="tickets")
    agent = relationship("Agent", back_populates="tickets")
    product = relationship("Product", back_populates="tickets")
