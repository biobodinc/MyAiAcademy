"""Base class for every Pydantic model the API exposes.

``json_schema_serialization_defaults_required`` makes fields that have defaults show up
as *required* in response schemas. Without it, every ``list`` with a default factory is
``optional`` in OpenAPI, and the generated TypeScript types force null checks on values
the service always sends.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
