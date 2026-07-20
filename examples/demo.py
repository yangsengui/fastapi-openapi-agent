from typing import Optional

from fastapi import FastAPI, HTTPException
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


@app.get("/health", tags=["system"], summary="Service health check")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/items", tags=["items"], summary="List inventory items")
def list_items(owner: Optional[str] = None) -> list[Item]:
    values = list(ITEMS.values())
    if owner:
        return [item for item in values if item.owner == owner]
    return values


@app.post("/items", tags=["items"], summary="Create an inventory item")
def create_item(payload: ItemCreate) -> Item:
    item_id = max(ITEMS) + 1
    item = Item(id=item_id, **payload.dict())
    ITEMS[item_id] = item
    return item


@app.get("/items/{item_id}", tags=["items"], summary="Get one inventory item")
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
    language="zh",
    allow_mutating_api_calls=True,
    llm_model_kwargs={"num_retries": 2},
)
