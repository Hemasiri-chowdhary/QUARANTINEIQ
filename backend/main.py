import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routers import router
from backend.database.migrate import prepare_database

load_dotenv()
prepare_database()

app = FastAPI(
    title="QuarantineIQ API",
    version="3.0.0",
    description="CI decision intelligence with real GitHub context and persistent engineering memory.",
)
frontend_origin = os.getenv("QUARANTINEIQ_FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "quarantineiq-api", "version": "3.0.0"}
