from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.mongodb import check_database_connection, client
from app.services.database import initialize_collections
from app.routers.meetings import router as meetings_router

app = FastAPI(
    title="DeciTrack API",
    description="AI-powered organizational memory and decision tracking",
    version="1.0.0"
)
app.include_router(meetings_router)


@app.on_event("startup")
def startup():
    initialize_collections()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Welcome to DeciTrack API"
    }


@app.get("/health")
def health_check():
    db_connected = check_database_connection()

    return {
        "status": "healthy" if db_connected else "degraded",
        "backend": "running",
        "database": "connected" if db_connected else "disconnected"
    }


@app.on_event("shutdown")
def shutdown():
    client.close()
