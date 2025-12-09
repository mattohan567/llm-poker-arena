"""FastAPI application for LLM Poker Arena."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_poker.config import settings
from llm_poker.api.schemas import HealthResponse
from llm_poker.api.routes import leaderboard, models, matches

# Create FastAPI app
app = FastAPI(
    title="LLM Poker Arena API",
    description="Multi-agent poker evaluation framework for testing LLMs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(leaderboard.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(matches.router, prefix="/api")


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "LLM Poker Arena API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns API status and configuration information.
    """
    # Count configured models
    api_keys = [
        settings.openai_api_key,
        settings.anthropic_api_key,
        settings.google_api_key,
        settings.groq_api_key,
        settings.mistral_api_key,
        settings.deepseek_api_key,
    ]
    models_configured = sum(1 for key in api_keys if key)

    # Check Supabase connection
    supabase_connected = bool(settings.supabase_url and settings.supabase_key)

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        supabase_connected=supabase_connected,
        models_configured=models_configured,
    )
