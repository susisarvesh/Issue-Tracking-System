from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from database import engine, Base
from routers import tickets, customers, agents, products

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Issue Ticketing Platform API")

# ---------------- ENABLE CORS ----------------
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # use ["*"] during dev if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(agents.router)
app.include_router(products.router)


@app.get("/")
def root():
    return {"message": "Ticketing API running 🚀"}
