from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models.schemas import FieldResult, InferResponse, RejectedField
from app.services.schema_inference import infer_field_type, validate_field_name


@dataclass
class RegisterResult:
    version: int
    inserted: dict[str, str] = field(default_factory=dict)
    # Names that turned out to exist already (another replica won the race).
    existing: dict[str, str] = field(default_factory=dict)


class RegistryRepository(Protocol):
    async def get_registry(self) -> dict[str, str]: ...
    async def current_version(self) -> int: ...
    async def register_fields(self, fields: dict[str, str], description: str) -> RegisterResult: ...


async def infer_and_register(
    samples: dict[str, list[Any]],
    repo: RegistryRepository,
    max_new_fields: int,
    max_total_fields: int,
) -> InferResponse:
    rejected: list[RejectedField] = []
    candidates: dict[str, str] = {}

    for name, values in samples.items():
        reason = validate_field_name(name)
        if reason:
            rejected.append(RejectedField(name=name, reason=reason))
        else:
            candidates[name] = infer_field_type(values)

    registry = await repo.get_registry()

    # Existing fields keep their registered type. The registry is append-only,
    # so a type is never changed after the fact.
    existing = [FieldResult(name=n, type=registry[n]) for n in candidates if n in registry]
    new_fields = {n: t for n, t in candidates.items() if n not in registry}

    capacity = max(0, min(max_new_fields, max_total_fields - len(registry)))
    accepted: dict[str, str] = {}
    for name, ftype in new_fields.items():
        if len(accepted) < capacity:
            accepted[name] = ftype
        else:
            rejected.append(RejectedField(name=name, reason="field_limit_reached"))

    if not accepted:
        return InferResponse(
            schema_version=await repo.current_version(),
            existing=existing,
            rejected=rejected,
        )

    result = await repo.register_fields(
        accepted, description=f"auto-detected: {', '.join(sorted(accepted))}"
    )
    existing.extend(FieldResult(name=n, type=t) for n, t in result.existing.items())
    return InferResponse(
        schema_version=result.version,
        registered=[FieldResult(name=n, type=t) for n, t in result.inserted.items()],
        existing=existing,
        rejected=rejected,
    )