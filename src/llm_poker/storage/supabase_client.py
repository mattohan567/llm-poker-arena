"""Supabase client initialization and connection management."""

from functools import lru_cache
from supabase import create_client, Client

from llm_poker.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Get a cached Supabase client instance.

    Returns:
        Supabase Client instance

    Raises:
        ValueError: If Supabase credentials are not configured
    """
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError(
            "Supabase credentials not configured. "
            "Set SUPABASE_URL and SUPABASE_KEY in your .env file."
        )

    return create_client(settings.supabase_url, settings.supabase_key)


def clear_client_cache():
    """Clear the cached client (useful for testing)."""
    get_supabase_client.cache_clear()
