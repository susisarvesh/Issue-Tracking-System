from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, SessionLocal
from models import Ticket, TicketStatus, Agent
from schemas import TicketCreate, TicketUpdate, TicketResponse
from datetime import datetime, timedelta
from ws_manager import manager   

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
        .order_by(func.count(Ticket.id).asc())  # ✅ fix ordering
        .first()
    )
    if not agent:
        raise HTTPException(status_code=400, detail="No available agents to assign")
    return agent.id


# ---------------- CREATE ----------------
@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    # ✅ Auto-assign agent if not provided
    agent_id = ticket.agent_id if ticket.agent_id is not None else assign_agent(db)

    db_ticket = Ticket(
        **ticket.dict(exclude={"agent_id"}),
        agent_id=agent_id,
        status=TicketStatus.assigned,
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)

    # 🔥 WebSocket notification
    import asyncio
    asyncio.create_task(manager.broadcast(f"🎫 Ticket created: {db_ticket.title} (ID {db_ticket.id})"))

    return db_ticket


# ---------------- READ ----------------
@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


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

    # 🔥 WebSocket notification
    import asyncio
    asyncio.create_task(manager.broadcast(f"✏️ Ticket updated: {db_ticket.title} (ID {db_ticket.id})"))

    return db_ticket


# ---------------- REQUEST CLOSE (Agent marks resolved) ----------------
@router.put("/{ticket_id}/resolve", response_model=TicketResponse)
def resolve_ticket(ticket_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status == TicketStatus.closed:
        raise HTTPException(status_code=400, detail="Ticket already closed")

    # Agent marks it pending customer approval
    ticket.status = TicketStatus.pending_customer
    db.commit()
    db.refresh(ticket)

    # 🔥 WebSocket notification
    import asyncio
    asyncio.create_task(manager.broadcast(f"🕒 Ticket pending customer approval: {ticket.title} (ID {ticket.id})"))

    # NOTE: BackgroundTasks runs immediately after response, not after 1 day.
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

    # 🔥 WebSocket notification
    import asyncio
    asyncio.create_task(manager.broadcast(f"✅ Ticket closed by customer: {ticket.title} (ID {ticket.id})"))

    return None  # ✅ 204 No Content


# ---------------- AUTO CLOSE ----------------
def auto_close_ticket(ticket_id: int):
    db = SessionLocal()  # ✅ new session for background task
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket and ticket.status == TicketStatus.pending_customer:
            if (datetime.utcnow() - ticket.updated_at) > timedelta(days=1):
                ticket.status = TicketStatus.closed
                ticket.closed_at = datetime.utcnow()
                db.commit()

                # 🔥 WebSocket notification
                import asyncio
                asyncio.run(manager.broadcast(f"⌛ Ticket auto-closed: {ticket.title} (ID {ticket.id})"))
    finally:
        db.close()
