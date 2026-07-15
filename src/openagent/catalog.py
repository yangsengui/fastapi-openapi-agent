from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from .responder import HTTP_METHODS, OperationHit, _rank_operations


READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}


class OperationMetadata(BaseModel):
    """Schema-free information used to select an OpenAPI operation."""

    operation_id: Optional[str] = None
    method: str
    path: str
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    parameters: List[str] = Field(default_factory=list)
    request_body: bool = False
    responses: List[str] = Field(default_factory=list)


class OperationContract(BaseModel):
    """Resolved operation contract returned after an operation is selected."""

    metadata: OperationMetadata
    risk: str
    openapi_operation: Dict[str, Any]
    component_schemas: Dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class _OperationRecord:
    method: str
    path: str
    operation: Dict[str, Any]
    path_parameters: List[Dict[str, Any]]


class OperationCatalog:
    """Public index for schema-free discovery and on-demand contract loading."""

    def __init__(self, openapi: Dict[str, Any]) -> None:
        self.openapi = openapi
        self._records = list(_iter_records(openapi))

    @classmethod
    def from_openapi(cls, openapi: Dict[str, Any]) -> "OperationCatalog":
        return cls(openapi)

    def list_operations(self) -> List[OperationMetadata]:
        return [_metadata(record, self.openapi) for record in self._records]

    def search_operations(
        self,
        query: str = "",
        *,
        method: Optional[str] = None,
        operation_id: Optional[str] = None,
        limit: int = 8,
    ) -> List[OperationMetadata]:
        records = self._records
        bounded_limit = max(1, min(int(limit), 100))
        if method:
            expected = method.upper()
            records = [record for record in records if record.method == expected]

        if operation_id:
            records = [
                record
                for record in records
                if record.operation.get("operationId") == operation_id
            ]
        elif query.strip():
            hits = [_hit(record, self.openapi) for record in records]
            ranked = _rank_operations(query, hits, bounded_limit)
            keys = {(hit.method, hit.path) for hit in ranked}
            records = [record for record in records if (record.method, record.path) in keys]
            order = {(hit.method, hit.path): index for index, hit in enumerate(ranked)}
            records.sort(key=lambda record: order[(record.method, record.path)])

        return [_metadata(record, self.openapi) for record in records[:bounded_limit]]

    def get_operation(self, operation_id: str) -> Optional[OperationContract]:
        record = self._find(operation_id=operation_id)
        return self._contract(record) if record else None

    def require_operation(self, operation_id: str) -> OperationContract:
        contract = self.get_operation(operation_id)
        if contract is None:
            raise KeyError(f"Operation not found: {operation_id}")
        return contract

    def find_operation(
        self,
        *,
        operation_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Optional[OperationContract]:
        record = self._find(operation_id=operation_id, method=method, path=path)
        return self._contract(record) if record else None

    def _find(
        self,
        *,
        operation_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Optional[_OperationRecord]:
        expected_method = method.upper() if method else None
        for record in self._records:
            if operation_id and record.operation.get("operationId") == operation_id:
                return record
            if path and expected_method and record.path == path and record.method == expected_method:
                return record
        return None

    def _contract(self, record: _OperationRecord) -> OperationContract:
        operation = _merged_operation(record, self.openapi)
        return OperationContract(
            metadata=_metadata(record, self.openapi),
            risk=_operation_risk(record.method, record.operation),
            openapi_operation=operation,
            component_schemas=_component_schemas_for_value(self.openapi, operation),
        )


def _iter_records(openapi: Dict[str, Any]):
    paths = openapi.get("paths") or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_parameters = _parameter_list(path_item.get("parameters"))
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            yield _OperationRecord(
                method=method.upper(),
                path=path,
                operation=operation,
                path_parameters=path_parameters,
            )


def _metadata(record: _OperationRecord, openapi: Dict[str, Any]) -> OperationMetadata:
    operation = _merged_operation(record, openapi)
    return OperationMetadata(
        operation_id=operation.get("operationId"),
        method=record.method,
        path=record.path,
        summary=operation.get("summary"),
        description=operation.get("description"),
        tags=list(operation.get("tags") or []),
        parameters=[
            _parameter_label(parameter, openapi)
            for parameter in _parameter_list(operation.get("parameters"))
        ],
        request_body="requestBody" in operation,
        responses=list((operation.get("responses") or {}).keys()),
    )


def _hit(record: _OperationRecord, openapi: Dict[str, Any]) -> OperationHit:
    metadata = _metadata(record, openapi)
    return OperationHit(
        method=metadata.method,
        path=metadata.path,
        operation_id=metadata.operation_id,
        summary=metadata.summary,
        description=metadata.description,
        tags=metadata.tags,
        parameters=metadata.parameters,
        request_body=metadata.request_body,
        responses=metadata.responses,
    )


def _merged_operation(
    record: _OperationRecord, openapi: Dict[str, Any]
) -> Dict[str, Any]:
    operation = dict(record.operation)
    inherited = [_resolve_parameter(item, openapi) for item in record.path_parameters]
    own = [
        _resolve_parameter(item, openapi)
        for item in _parameter_list(record.operation.get("parameters"))
    ]
    if inherited or own:
        merged: Dict[tuple[str, str], Dict[str, Any]] = {}
        unkeyed: List[Dict[str, Any]] = []
        for parameter in inherited + own:
            name = parameter.get("name")
            location = parameter.get("in")
            if isinstance(name, str) and isinstance(location, str):
                merged[(location, name)] = parameter
            else:
                unkeyed.append(parameter)
        operation["parameters"] = list(merged.values()) + unkeyed
    return operation


def _parameter_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _resolve_parameter(parameter: Dict[str, Any], openapi: Dict[str, Any]) -> Dict[str, Any]:
    parameters = ((openapi.get("components") or {}).get("parameters") or {})
    current = parameter
    seen: Set[str] = set()
    prefix = "#/components/parameters/"
    while True:
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith(prefix) or ref in seen:
            return current
        seen.add(ref)
        name = _decode_pointer_token(ref[len(prefix) :])
        resolved = parameters.get(name)
        if not isinstance(resolved, dict):
            return current
        current = resolved


def _decode_pointer_token(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def _parameter_label(parameter: Dict[str, Any], openapi: Dict[str, Any]) -> str:
    resolved = _resolve_parameter(parameter, openapi)
    name = resolved.get("name")
    location = resolved.get("in")
    if name and location:
        return f"{name} ({location})"
    return str(name or parameter.get("$ref") or "")


def _operation_risk(method: str, operation: Dict[str, Any]) -> str:
    metadata = operation.get("x-acp-operation") or {}
    risk = metadata.get("risk") if isinstance(metadata, dict) else None
    if isinstance(risk, str) and risk.strip():
        return risk.strip()
    return "read_only" if method.upper() in READ_ONLY_METHODS else "mutating"


def _component_schemas_for_value(
    openapi: Dict[str, Any], value: Any
) -> Dict[str, Any]:
    schemas = ((openapi.get("components") or {}).get("schemas") or {})
    names: Set[str] = set()
    _collect_refs(value, names)
    previous_size = -1
    while previous_size != len(names):
        previous_size = len(names)
        for name in list(names):
            schema = schemas.get(name)
            if schema:
                _collect_refs(schema, names)
    return {name: schemas[name] for name in sorted(names) if name in schemas}


def _collect_refs(value: Any, names: Set[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        prefix = "#/components/schemas/"
        if isinstance(ref, str) and ref.startswith(prefix):
            names.add(_decode_pointer_token(ref[len(prefix) :]))
        for child in value.values():
            _collect_refs(child, names)
    elif isinstance(value, list):
        for child in value:
            _collect_refs(child, names)
