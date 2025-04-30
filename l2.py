import time
import json
import threading
from datetime import datetime
import websocket

# Subscription message for Kraken V2
book_message = {
    "method": "subscribe",
    "params": {
        "channel": "book",
        "symbol": ["BTC/USD"],
        "depth": 100,
        "snapshot":True
    }
}

def ws_open_book(ws):
    print("✅ Kraken V2 WebSocket connection opened.")
    ws.send(json.dumps(book_message))

def on_message(ws, message):
    data = json.loads(message)
    # Ignore non-data messages (like system status)
    if isinstance(data, dict) and data.get("channel") != "book":
        return
    print(f"📩 [{datetime.now().strftime('%H:%M:%S')}] Order Book Data:")
    print(json.dumps(data, indent=2))  # Pretty print for readability
    time.sleep(0.5)

def on_error(ws, error):
    print("❌ WebSocket Error:", error)

def on_close(ws, code, msg):
    print(f"🔌 WebSocket closed. Code: {code}, Reason: {msg}")

def run_websocket_book():
    ws = websocket.WebSocketApp(
        'wss://ws.kraken.com/v2',
        on_open=ws_open_book,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# Start WebSocket in a separate thread
ws_thread_book = threading.Thread(target=run_websocket_book, daemon=False)
ws_thread_book.start()

