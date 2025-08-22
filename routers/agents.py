from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Agent, Ticket
from schemas import AgentCreate, AgentUpdate, AgentResponse, TicketResponse
from typing import List

router = APIRouter(prefix="/agents", tags=["Agents"])


# ---------------- CREATE ----------------
@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    # case-insensitive email check
    existing = db.query(Agent).filter(func.lower(Agent.email) == agent.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    db_agent = Agent(**agent.dict())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)

    return db_agent


# ---------------- READ ALL (with pagination) ----------------
@router.get("/", response_model=List[AgentResponse])
def get_agents(skip: int = 0, limit: int = 25, db: Session = Depends(get_db)):
    return db.query(Agent).offset(skip).limit(limit).all()


# ---------------- READ ONE ----------------
@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ---------------- UPDATE ----------------
@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: int, updated: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = updated.dict(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        existing = (
            db.query(Agent)
            .filter(func.lower(Agent.email) == update_data["email"].lower(), Agent.id != agent_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered with another agent",
            )

    for key, value in update_data.items():
        setattr(agent, key, value)

    db.commit()
    db.refresh(agent)

    return agent


# ---------------- DELETE ----------------
@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    db.delete(agent)
    db.commit()

    return None


# ---------------- GET AGENT TICKETS ----------------
@router.get("/{agent_id}/tickets", response_model=List[TicketResponse])
def get_agent_tickets(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return db.query(Ticket).filter(Ticket.agent_id == agent_id).all()
