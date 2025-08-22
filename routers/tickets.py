from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, SessionLocal
from models import Ticket, TicketStatus, Agent
from schemas import TicketCreate, TicketUpdate, TicketResponse
from datetime import datetime, timedelta
from typing import List

router = APIRouter(prefix="/tickets", tags=["Tickets"])


# ---------------- Helper: Auto-assign agent ----------------
def assign_agent(db: Session) -> int:
    """
    Find the agent with the least number of active (non-closed) tickets.
    Returns the agent_id.
    """
    agent = (
        db.query(Agent.id, func.count(Ticket.id).label("active_tickets"))
        .outerjoin(Ticket, (Ticket.agent_id == Agent.id) & (Ticket.status != TicketStatus.closed))
        .group_by(Agent.id)
        .order_by(func.count(Ticket.id).asc())
        .first()
    )
    if not agent:
        raise HTTPException(status_code=400, detail="No available agents to assign")
    return agent.id


# ---------------- CREATE ----------------
@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    agent_id = ticket.agent_id if ticket.agent_id is not None else assign_agent(db)

    db_ticket = Ticket(
        **ticket.dict(exclude={"agent_id"}),
        agent_id=agent_id,
        status=TicketStatus.assigned,
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)

    return db_ticket


# ---------------- READ ONE ----------------
@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


# ---------------- READ ALL ----------------
@router.get("/", response_model=List[TicketResponse])
def get_all_tickets(db: Session = Depends(get_db)):
    return db.query(Ticket).all()


# ---------------- UPDATE ----------------
@router.put("/{ticket_id}", response_model=TicketResponse)
def update_ticket(ticket_id: int, ticket: TicketUpdate, db: Session = Depends(get_db)):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    for key, value in ticket.dict(exclude_unset=True).items():
        setattr(db_ticket, key, value)

    db.commit()
    db.refresh(db_ticket)

    return db_ticket


# ---------------- REQUEST CLOSE (Agent marks resolved) ----------------
@router.put("/{ticket_id}/resolve", response_model=TicketResponse)
def resolve_ticket(ticket_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status == TicketStatus.closed:
        raise HTTPException(status_code=400, detail="Ticket already closed")

    ticket.status = TicketStatus.pending_customer
    db.commit()
    db.refresh(ticket)

    # Run background task to auto-close after 1 day
    background_tasks.add_task(auto_close_ticket, ticket_id)

    return ticket


# ---------------- CUSTOMER APPROVAL (final close) ----------------
@router.put("/{ticket_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
def approve_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != TicketStatus.pending_customer:
        raise HTTPException(status_code=400, detail="Ticket not waiting for approval")

    ticket.status = TicketStatus.closed
    ticket.closed_at = datetime.utcnow()
    db.commit()

    return None  # ✅ 204 No Content


# ---------------- AUTO CLOSE ----------------
def auto_close_ticket(ticket_id: int):
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket and ticket.status == TicketStatus.pending_customer:
            if (datetime.utcnow() - ticket.updated_at) > timedelta(days=1):
                ticket.status = TicketStatus.closed
                ticket.closed_at = datetime.utcnow()
                db.commit()
    finally:
        db.close()
