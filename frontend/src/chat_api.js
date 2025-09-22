// src/api/chat.js

// Axios is used to send HTTP requests to your FastAPI backend
import axios from "axios";

// Your backend base URL (adjust if deployed)
const BASE_URL = "http://localhost:8000";

// This function sends a POST request to /chat with the full message history
export async function sendChat(messages) {
  const payload = {
    messages, // array of { role: "user" | "assistant", content: "..." }
  };

  // POST to FastAPI /chat endpoint
  const response = await axios.post(`${BASE_URL}/chat`, payload, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });

  // Return the assistant's reply (assumes response contains { answer: "..." })
  return response.data;
}
