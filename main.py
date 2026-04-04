import sqlite3
import requests
import os
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 🏦 DATABASE INITIALIZATION
# ==========================================
def init_db():
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    # Vault Portfolio Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY,
            buying_power REAL
        )
    """)
    # Nova AI History Table (NEW!)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nova_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM portfolio")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO portfolio (buying_power) VALUES (25000.00)")
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🏦 VAULT FINTECH STATION
# ==========================================
@app.get("/api/portfolio")
def get_portfolio():
    conn = sqlite3.connect("vault.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT buying_power FROM portfolio LIMIT 1")
    data = cursor.fetchone()
    conn.close()
    return dict(data)

class TradeRequest(BaseModel):
    amount: float
    action: str

@app.post("/api/trade")
def execute_trade(trade: TradeRequest):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT buying_power FROM portfolio LIMIT 1")
    current_bp = cursor.fetchone()[0]
    
    if trade.action == "Buy":
        if trade.amount > current_bp:
            return {"status": "error", "message": "Insufficient funds"}
        new_bp = current_bp - trade.amount
    else:
        new_bp = current_bp + trade.amount
        
    cursor.execute("UPDATE portfolio SET buying_power = ?", (new_bp,))
    conn.commit()
    conn.close()
    return {"status": "success", "new_buying_power": new_bp}


# ==========================================
# ✨ NOVA AI STATION
# ==========================================

# --- NEW: Get Chat History ---
@app.get("/api/nova/history")
def get_nova_history():
    conn = sqlite3.connect("vault.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Grab the latest 15 chats
    cursor.execute("SELECT id, title, created_at FROM nova_history ORDER BY created_at DESC LIMIT 15")
    chats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"status": "success", "history": chats}

# --- NEW: Save Chat Title ---
class ChatSession(BaseModel):
    title: str

@app.post("/api/nova/history")
def save_nova_history(session: ChatSession):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO nova_history (title) VALUES (?)", (session.title,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# --- Existing Chat AI ---
class ChatRequest(BaseModel):
    prompt: str
    
@app.post("/api/nova/chat")
def nova_chat(req: ChatRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "API Key is missing from the server."}
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    try:
        response = model.generate_content(req.prompt)
        return {"status": "success", "reply": response.text}
    except Exception as e:
        return {"status": "error", "reply": str(e)}