import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- CORS SETUP ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE SETUP (The Pantry) ---
def init_db():
    # 1. Connect to a database (this creates 'vault.db' if it doesn't exist)
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    
    # 2. Create a table for our portfolio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY,
            buying_power REAL,
            active_trades INTEGER,
            status TEXT
        )
    """)
    
    # 3. If the table is empty, insert our starting data
    cursor.execute("SELECT COUNT(*) FROM portfolio")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO portfolio (buying_power, active_trades, status) VALUES (25000.00, 4, 'Market Open')")
        conn.commit()
        
    conn.close()

# Run the setup function as soon as the file loads
init_db()


# --- API ROUTES ---
@app.get("/")
def health_check():
    return {"status": "success", "message": "Vault API is running perfectly."}

@app.get("/api/portfolio")
def get_portfolio():
    # 1. Open the pantry
    conn = sqlite3.connect("vault.db")
    conn.row_factory = sqlite3.Row # This makes the data format nicely into JSON
    cursor = conn.cursor()
    
    # 2. Grab the data from the database
    cursor.execute("SELECT * FROM portfolio LIMIT 1")
    data = cursor.fetchone()
    
    # 3. Close the pantry
    conn.close()
    
    # 4. Send it to React
    return dict(data)

from pydantic import BaseModel

# 1. Define what an "Order" looks like so Python knows what to expect
class TradeRequest(BaseModel):
    amount: float
    action: str  # "Buy" or "Sell"

# 2. Create the POST route to process the trade
@app.post("/api/trade")
def execute_trade(trade: TradeRequest):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    
    # Grab the current buying power from the database
    cursor.execute("SELECT buying_power FROM portfolio LIMIT 1")
    current_bp = cursor.fetchone()[0]
    
    # Calculate the new balance
    if trade.action == "Buy":
        if trade.amount > current_bp:
            return {"status": "error", "message": "Insufficient funds"}
        new_bp = current_bp - trade.amount
    else:
        new_bp = current_bp + trade.amount
        
    # UPDATE the database permanently
    cursor.execute("UPDATE portfolio SET buying_power = ?", (new_bp,))
    conn.commit()
    conn.close()
    
    # Send the new permanent balance back to React
    return {"status": "success", "new_buying_power": new_bp}