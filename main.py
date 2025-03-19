from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import httpx
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

app = FastAPI(title="Vivian - Mental Health companion")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory - ensure this directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

# Memory storage - replace with a database in production
user_conversations = {}
user_profiles = {}

# Pydantic models
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    user_id: str
    message: str
    
class ProfileRequest(BaseModel):
    user_id: str
    name: Optional[str] = None
    preferences: Optional[Dict] = None

class ChatResponse(BaseModel):
    response: str
    emotion_detected: Optional[str] = None
    suggestions: Optional[List[str]] = None
    
# Helper functions
def detect_crisis(message: str) -> bool:
    crisis_keywords = ["suicide", "kill myself", "end my life", "don't want to live", 
                      "want to die", "harm myself", "self harm"]
    return any(keyword in message.lower() for keyword in crisis_keywords)

def get_crisis_resources() -> str:
    return """
    I notice you're expressing some concerning thoughts. Please remember you're not alone.
    
    Here are some immediate resources that can help:
    • National Suicide Prevention Lifeline: 988 or 1-800-273-8255 (24/7)
    • Crisis Text Line: Text HOME to 741741
    • If you're in immediate danger, please call 911 or go to your nearest emergency room
    
    Would it be okay if we talk about what you're experiencing right now?
    """

def create_system_prompt(user_id: str) -> str:
    profile = user_profiles.get(user_id, {})
    name = profile.get("name", "there")
    
    return f"""
    You are Vivian, an empathetic and supportive mental health companion. Your goal is to provide 
    emotional support, guidance, and a safe space for {name}. Follow these guidelines:
    
    1. Be warm, empathetic, and conversational - like a trusted friend or therapist
    2. Use active listening techniques and reflect back feelings
    3. Incorporate CBT techniques when appropriate
    4. Ask open-ended questions to explore thoughts and feelings
    5. Validate emotions without judgment
    6. Avoid toxic positivity or dismissing negative feelings
    7. Suggest practical coping strategies when relevant
    8. Keep responses concise but thoughtful (2-3 paragraphs maximum)
    9. Respect boundaries and privacy
    10. Never claim to be a replacement for professional therapy
    
    Remember past conversations for continuity and personalization.
    """

async def get_nova_response(user_id: str, message: str) -> ChatResponse:
    # Check for crisis content
    if detect_crisis(message):
        return ChatResponse(
            response=get_crisis_resources(),
            emotion_detected="distress",
            suggestions=["Talk to a trusted person", "Focus on breathing", "Call a helpline"]
        )
    
    # Get conversation history or initialize
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    
    # Add current message to history
    user_conversations[user_id].append({"role": "user", "content": message})
    
    # Prepare messages for API
    messages = [
        {"role": "system", "content": create_system_prompt(user_id)},
    ]
    
    # Add up to 10 previous messages for context
    if len(user_conversations[user_id]) > 1:
        for msg in user_conversations[user_id][-10:]:
            messages.append(msg)
    
    # Call Groq API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1024
                },
                timeout=30.0
            )
            
            response_data = response.json()
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Error from LLM provider")
                
            nova_response = response_data["choices"][0]["message"]["content"]
            
            # Store assistant response
            user_conversations[user_id].append({"role": "assistant", "content": nova_response})
            
            # In a real system, you would use a more sophisticated emotion detection model
            emotion_detected = None
            suggestions = None
            
            return ChatResponse(
                response=nova_response,
                emotion_detected=emotion_detected,
                suggestions=suggestions
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with LLM: {str(e)}")

# FastAPI routes
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("index.html")

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await get_nova_response(request.user_id, request.message)

@app.post("/api/profile")
async def update_profile(profile: ProfileRequest):
    user_id = profile.user_id
    
    if user_id not in user_profiles:
        user_profiles[user_id] = {}
    
    if profile.name:
        user_profiles[user_id]["name"] = profile.name
    
    if profile.preferences:
        if "preferences" not in user_profiles[user_id]:
            user_profiles[user_id]["preferences"] = {}
        user_profiles[user_id]["preferences"].update(profile.preferences)
    
    return {"status": "success", "message": "Profile updated"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}