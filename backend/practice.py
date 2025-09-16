## DELETe ME SOOn

from fastapi import FastAPI, HTTPException

items = []

app = FastAPI(title="Inventi Demo Backend")

@app.get("/")
def root():
    return {"Hello" : "Worldsssss"}

@app.post("/items")
def create_item(item: str):
    items.append(item)
    return items

@app.get("/items/{item_id}")
def get_item(item_id: int) -> str:
    item = items[item_id]
    return item