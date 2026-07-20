# OpenAPI quality guide

A high-quality OpenAPI document is more than something that renders in Swagger UI. For an Agent, it is simultaneously a tool catalog, argument guide, response contract, and risk signal.

## Fields that matter most to the Agent

| Priority | Field | Why it matters | Recommendation |
| --- | --- | --- | --- |
| P0 | `operationId` | Stable operation selection and invocation | Globally unique, durable, and named as verb plus business object |
| P0 | Parameter and request-body schemas | Correct call arguments | Define required fields, types, constraints, formats, and descriptions |
| P0 | responses | Understand success and failure | Cover the primary success response and common 4xx outcomes |
| P1 | `summary` | Fast intent matching | Use an action plus object, not generic text such as “Handle request” |
| P1 | `description` | Business preconditions and boundaries | Document visibility, side effects, state restrictions, and pagination |
| P1 | `tags` | Narrow the business domain | Use stable domain names rather than temporary team names |
| P1 | Schema field descriptions | Fill IDs, enums, dates, and amounts correctly | Explain business meaning rather than repeating the field name |
| P2 | examples | Demonstrate valid formats | Every example should validate against the current schema |
| P2 | security | Express authentication and scopes | Keep the document aligned with the real middleware policy |

## Recommended operation IDs

Good names:

```text
list_inventory_items
get_inventory_item
create_inventory_item
cancel_purchase_order
preview_monthly_report
```

Avoid:

```text
items_get
handle_request
api_v2_action
postData
```

Do not make URL versions or framework-generated details part of a permanent tool name. A stable `operationId` reduces Agent behavior drift when paths change.

## Complete FastAPI example

```python
from enum import Enum
from typing import List, Optional

from fastapi import FastAPI, Header, Query
from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class OrderSummary(BaseModel):
    id: str = Field(description="Order ID", example="ord_01JABC")
    status: OrderStatus = Field(description="Current order status")
    total_cents: int = Field(ge=0, description="Order total in cents", example=12900)


app = FastAPI(
    title="Orders API",
    version="1.0.0",
    description="Query and manage orders for the current tenant. All timestamps use RFC 3339 UTC.",
)


@app.get(
    "/orders",
    operation_id="list_orders",
    summary="List orders",
    description="Return orders visible to the current tenant, newest first.",
    tags=["orders"],
    response_model=List[OrderSummary],
    responses={
        401: {"description": "The access token is missing or invalid"},
        403: {"description": "The caller cannot access this tenant"},
    },
)
def list_orders(
    tenant_id: str = Header(description="Tenant ID", example="tenant_demo"),
    status: Optional[OrderStatus] = Query(default=None, description="Filter by order status"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of orders"),
) -> List[OrderSummary]:
    return []
```

## Risk metadata

OpenAgent classifies risk from the HTTP method by default. If a `POST` is a genuinely side-effect-free preview, it can be marked explicitly:

```python
@app.post(
    "/reports/preview",
    operation_id="preview_report",
    openapi_extra={"x-acp-operation": {"risk": "read_only"}},
)
def preview_report(payload: ReportRequest) -> ReportPreview:
    ...
```

!!! danger

    Never mislabel an operation to bypass mutating-call protection. Any operation that creates a resource, sends a message, charges money, changes state, or starts an asynchronous job must remain `mutating`.

## Pre-release checklist

- [ ] Every Agent-visible operation has a unique and stable `operationId`.
- [ ] Each `summary` communicates the action and business object without relying on the path.
- [ ] Descriptions explain preconditions, side effects, visibility, and pagination.
- [ ] Path parameters are required and match the real route types.
- [ ] IDs, money, dates, time zones, enums, and units are documented.
- [ ] Request-body required fields, nested objects, and constraints are complete.
- [ ] Success responses have concrete schemas and common failures have status codes.
- [ ] Examples validate against the schema and contain no real sensitive data.
- [ ] Security schemes and scopes match production authentication.
- [ ] No mutating operation is incorrectly marked `read_only`.
- [ ] `/_agent/openapi` is checked as the final runtime schema rather than trusting a stale file.

## Evaluating Agent quality

Prepare three test questions for every critical operation:

1. **Explicit intent:** names the business action and should select the right operation immediately.
2. **Natural phrasing:** uses language from real users and should still match the correct `operationId`.
3. **Ambiguous request:** omits required input; the Agent should ask or report what is missing instead of guessing.

Keep these prompts and expected operations as regression cases. Re-run them after OpenAPI changes, model upgrades, or prompt changes.
