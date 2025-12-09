"""Models API routes."""

from fastapi import APIRouter

from llm_poker.config import DEFAULT_MODELS, settings
from llm_poker.api.schemas import ModelInfo, ModelsListResponse

router = APIRouter(prefix="/models", tags=["models"])


def _check_api_key_configured(provider: str) -> bool:
    """Check if API key is configured for a provider."""
    provider_key_map = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.google_api_key,
        "google": settings.google_api_key,
        "groq": settings.groq_api_key,
        "mistral": settings.mistral_api_key,
        "deepseek": settings.deepseek_api_key,
    }
    return bool(provider_key_map.get(provider, ""))


@router.get("", response_model=ModelsListResponse)
async def list_models() -> ModelsListResponse:
    """
    List all default models available for poker matches.

    Returns model information including whether the API key is configured.
    """
    models = []

    for model_id in DEFAULT_MODELS:
        provider, name = model_id.split("/", 1)
        models.append(
            ModelInfo(
                id=model_id,
                provider=provider,
                name=name,
                configured=_check_api_key_configured(provider),
            )
        )

    return ModelsListResponse(
        models=models,
        total=len(models),
    )


@router.get("/configured", response_model=ModelsListResponse)
async def list_configured_models() -> ModelsListResponse:
    """
    List only models that have API keys configured.

    Use this endpoint to get models that are ready to use.
    """
    models = []

    for model_id in DEFAULT_MODELS:
        provider, name = model_id.split("/", 1)
        if _check_api_key_configured(provider):
            models.append(
                ModelInfo(
                    id=model_id,
                    provider=provider,
                    name=name,
                    configured=True,
                )
            )

    return ModelsListResponse(
        models=models,
        total=len(models),
    )
