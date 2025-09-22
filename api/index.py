# api/index.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Property Management API")

# CORS: allow frontend on the same Vercel domain and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later with your vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/hello")
def hello():
    return {"message": "Hello from FastAPI on Vercel!"}

# Basic chat payload models for your /api/chat
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    collection_focus: Optional[str] = None

@app.post("/api/chat")
def chat_endpoint(chat_request: ChatRequest):
    user_text = "\n".join(m.content for m in chat_request.messages if m.role == "user").strip()
    if not user_text:
        return {"response": "No user message found."}

    # Replace below with your hybrid_generate_answer or generate_answer
    # from your backend. Keep it simple first to validate deployment.
    response = f"You said: {user_text} (demo response)"
    return {"intent": "general", "response": response, "relevant_data": None}
# You can expand with more endpoints as needed