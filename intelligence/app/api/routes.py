from fastapi import APIRouter, Depends

from app.clients.postgres_client import get_repository
from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import InferRequest, InferResponse
from app.services.registry_service import RegistryRepository, infer_and_register

logger = get_logger(__name__)
router = APIRouter()


@router.post("/v1/infer", response_model=InferResponse)
async def infer(request: InferRequest, repo: RegistryRepository = Depends(get_repository)):
    """Infers types for unknown keys and registers new ones as a new schema version."""
    response = await infer_and_register(
        request.samples,
        repo,
        max_new_fields=settings.max_new_fields_per_request,
        max_total_fields=settings.max_total_fields,
    )
    logger.info(
        "infer_completed",
        schema_version=response.schema_version,
        registered=len(response.registered),
        existing=len(response.existing),
        rejected=len(response.rejected),
    )
    return response