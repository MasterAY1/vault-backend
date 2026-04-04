import sqlite3
import os
import json
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

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
    cursor.execute("CREATE TABLE IF NOT EXISTS portfolio (id INTEGER PRIMARY KEY, buying_power REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS nova_history (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, messages TEXT DEFAULT '[]', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    
    # NEW: Settings Table for Global Consciousness
    cursor.execute("CREATE TABLE IF NOT EXISTS nova_settings (id INTEGER PRIMARY KEY, global_memory TEXT)")
    
    cursor.execute("SELECT COUNT(*) FROM portfolio")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO portfolio (buying_power) VALUES (25000.00)")
        
    cursor.execute("SELECT COUNT(*) FROM nova_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO nova_settings (global_memory) VALUES ('')")
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🏦 VAULT FINTECH STATION (Unchanged)
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
        if trade.amount > current_bp: return {"status": "error", "message": "Insufficient funds"}
        new_bp = current_bp - trade.amount
    else:
        new_bp = current_bp + trade.amount
    cursor.execute("UPDATE portfolio SET buying_power = ?", (new_bp,))
    conn.commit()
    conn.close()
    return {"status": "success", "new_buying_power": new_bp}

# ==========================================
# ✨ NOVA SETTINGS STATION (NEW!)
# ==========================================
class SettingsRequest(BaseModel):
    global_memory: str

@app.get("/api/nova/settings")
def get_settings():
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT global_memory FROM nova_settings LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return {"status": "success", "global_memory": row[0] if row else ""}

@app.post("/api/nova/settings")
def update_settings(req: SettingsRequest):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE nova_settings SET global_memory = ?", (req.global_memory,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ==========================================
# ✨ NOVA AI STATION
# ==========================================
@app.get("/api/nova/history")
def get_nova_history():
    conn = sqlite3.connect("vault.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at FROM nova_history ORDER BY created_at DESC LIMIT 15")
    chats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"status": "success", "history": chats}

@app.get("/api/nova/history/{chat_id}")
def get_single_chat(chat_id: int):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT messages FROM nova_history WHERE id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]: return {"status": "success", "messages": json.loads(row[0])}
    return {"status": "error", "messages": []}

class ChatRequest(BaseModel):
    chat_id: Optional[int] = None
    prompt: str
    
@app.post("/api/nova/chat")
def nova_chat(req: ChatRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return {"error": "API Key is missing."}
    
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    
    # FETCH CUSTOM INSTRUCTIONS FROM DATABASE
    cursor.execute("SELECT global_memory FROM nova_settings LIMIT 1")
    setting_row = cursor.fetchone()
    system_instruction = setting_row[0] if setting_row and setting_row[0] else "You are Nova, a helpful AI assistant."
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        system_instruction=system_instruction
    )
    
    db_messages = []
    if req.chat_id:
        cursor.execute("SELECT messages FROM nova_history WHERE id = ?", (req.chat_id,))
        row = cursor.fetchone()
        if row and row[0]: db_messages = json.loads(row[0])
    else:
        title = " ".join(req.prompt.split()[:4]) + "..."
        cursor.execute("INSERT INTO nova_history (title, messages) VALUES (?, ?)", (title, "[]"))
        req.chat_id = cursor.lastrowid

    gemini_history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in db_messages]

    try:
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(req.prompt)
        
        db_messages.append({"id": len(db_messages)+1, "role": "user", "content": req.prompt})
        db_messages.append({"id": len(db_messages)+2, "role": "ai", "content": response.text})
        
        cursor.execute("UPDATE nova_history SET messages = ? WHERE id = ?", (json.dumps(db_messages), req.chat_id))
        conn.commit()
        conn.close()
        
        return {"status": "success", "reply": response.text, "chat_id": req.chat_id}
    except Exception as e:
        conn.close()
        return {"status": "error", "reply": str(e)}