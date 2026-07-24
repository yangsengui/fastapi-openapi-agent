from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from openagent.fastapi import install_openapi_agent


class ItemCreate(BaseModel):
    name: str
    owner: str
    priority: int = 1


class Item(ItemCreate):
    id: int


app = FastAPI(title="Demo Inventory API", version="0.1.0")

ITEMS = {
    1: Item(id=1, name="Laptop", owner="platform", priority=2),
    2: Item(id=2, name="Router", owner="network", priority=1),
}


@app.get(
    "/health",
    operation_id="get_service_health",
    tags=["system"],
    summary="Get service health",
    description="Return the current health status of the demo inventory service.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/items",
    operation_id="list_inventory_items",
    tags=["items"],
    summary="List inventory items",
    description="Return inventory items, optionally filtered by the owning team.",
)
def list_items(
    owner: Optional[str] = Query(
        default=None,
        description="Return only inventory items owned by this team.",
    ),
) -> list[Item]:
    values = list(ITEMS.values())
    if owner:
        return [item for item in values if item.owner == owner]
    return values


@app.post(
    "/items",
    operation_id="create_inventory_item",
    tags=["items"],
    summary="Create an inventory item",
    description=(
        "Create a new inventory item. This mutating operation is not executable "
        "by the agent in the default demo."
    ),
)
def create_item(payload: ItemCreate) -> Item:
    item_id = max(ITEMS) + 1
    item = Item(id=item_id, **payload.dict())
    ITEMS[item_id] = item
    return item


@app.get(
    "/items/{item_id}",
    operation_id="get_inventory_item",
    tags=["items"],
    summary="Get one inventory item",
    description="Return one inventory item by its unique numeric identifier.",
)
def get_item(item_id: int) -> Item:
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


install_openapi_agent(
    app,
    title="OpenAPI-aware Demo API Agent",
    welcome_title="How can I help with your data?",
    description="Ask questions about the demo inventory OpenAPI schema.",
    llm_model_kwargs={"num_retries": 2},
)
