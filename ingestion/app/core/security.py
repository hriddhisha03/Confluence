from fastapi import Header, HTTPException, status
from app.core.config import settings

async def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:

    """
    Simple shared-secret auth for the ingestion edge.

    Production note: swap this for per-client API keys stored hashed in
    Postgres (with issue/revoke support) or an upstream API gateway doing
    OAuth2/JWT validation before requests reach this service.
    """
    
    if x_api_key is None or x_api_key not in settings.valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
        
    return x_api_key