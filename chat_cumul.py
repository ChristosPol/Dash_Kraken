import pandas as pd
import json
import threading
import math
import websocket
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go

# ------------------------------------------------------------------------------
# Global Variables & Parameters
# ------------------------------------------------------------------------------
# Current order book state: a dictionary mapping (side, binned_price) -> qty
current_order_book = {}  # keys: tuple like ("bid", 84800) or ("ask", 84900)
# Historical record of snapshots (each row records a snapshot of the current state)
historical_data = pd.DataFrame(columns=["snapshot_id", "side", "price", "qty"])
# Counter for snapshots (each Dash timer tick increases it)
snapshot_id = 0
last_trade_price = None
# Define the desired price increment for binning (e.g., 100)
PRICE_INCREMENT = 1
trade_price_history = []  # stores (snapshot_id, price)

# ------------------------------------------------------------------------------
# Helper Function to Bin Prices
# ------------------------------------------------------------------------------
def bin_price(price, increment):
    """
    Floors the price to the lower increment.
    Example: if price = 84855 and increment = 100, returns 84800.
    """
    return math.floor(price / increment) * increment

# ------------------------------------------------------------------------------
# Kraken WebSocket Subscription Message
# ------------------------------------------------------------------------------
book_message = {
    "method": "subscribe",
    "params": {
        "channel": "book",
        "symbol": ["SOL/USD"],
        "depth": 1000,      
        "snapshot": True
    }
}

trades_message = {
    "method": "subscribe",
    "params": {
        "symbol": ["SOL/USD"],
        "channel": "trade"
    }
}


message_ready = json.dumps(book_message)
message_ready_trades = json.dumps(trades_message)




# ------------------------------------------------------------------------------
# WebSocket Event Handlers
# ------------------------------------------------------------------------------
def ws_open(ws):
    print("✅ WebSocket connection opened.")
    ws.send(message_ready)
    ws.send(message_ready_trades)

def on_message(ws, message):
    global current_order_book

    
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        print("❌ Failed to decode message")
        return

    if isinstance(data, dict) and data.get("channel") == "trade":
        trades = data.get("data", [])
        if trades:
            global last_trade_price  # ✅ THIS IS MISSING
            trade = trades[-1]
            last_trade_price = float(trade.get("price"))
            print(f"💰 Last Trade: {last_trade_price}")
        return

    # # Handle subscription confirmation or heartbeat
    # if isinstance(data, dict):
    #     if data.get("event") == "subscribe":
    #         print(f"✅ Subscribed to: {data.get('channel')}")
    #     elif data.get("channel") == "heartbeat":
    #         print("💓 Heartbeat")
    #     return

    # Handle actual order book data (snapshot or update)
    if isinstance(data, dict) and data.get("channel") == "book":
        msg_type = data.get("type")
        updates = data.get("data", [])

        if not updates:
            return

        # Kraken v2 wraps book updates in a list, usually with one item
        update = updates[0]
        bids = update.get("bids", [])
        asks = update.get("asks", [])

        if msg_type == "snapshot":
            current_order_book.clear()
            print("📸 Received full snapshot")
            
        # Handle both snapshot and update by applying price/qty changes
        for bid in bids:
            price = bin_price(float(bid["price"]), PRICE_INCREMENT)
            qty = float(bid["qty"])
            key = ("bid", price)
            if qty == 0:
                current_order_book.pop(key, None)
            else:
                current_order_book[key] = qty

        for ask in asks:
            price = bin_price(float(ask["price"]), PRICE_INCREMENT)
            qty = float(ask["qty"])
            key = ("ask", price)
            if qty == 0:
                current_order_book.pop(key, None)
            else:
                current_order_book[key] = qty

        print(f"🔄 {msg_type.upper()} | Bids: {len(bids)}, Asks: {len(asks)} | Book Size: {len(current_order_book)}")

def on_error(ws, error):
    print("❌ WebSocket Error:", error)

def on_close(ws, code, msg):
    print(f"🔌 WebSocket closed. Code: {code}, Reason: {msg}")

def run_websocket_book():
    ws = websocket.WebSocketApp(
        "wss://ws.kraken.com/v2",
        on_open=ws_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ------------------------------------------------------------------------------
# Start the WebSocket in a Separate Thread
# ------------------------------------------------------------------------------
ws_thread_book = threading.Thread(target=run_websocket_book, daemon=False)
ws_thread_book.start()

# ------------------------------------------------------------------------------
# Create the Dash App for Visualization
# ------------------------------------------------------------------------------
app = Dash(__name__)

app.layout = html.Div([
    html.H2("Kraken BTC/USD Order Book Depth Heatmap (Historical Snapshots)"),
    dcc.Graph(id="heatmap"),
    dcc.Interval(id="interval", interval=500, n_intervals=0)  # Update every 1 second
])

# ------------------------------------------------------------------------------
# Dash Callback to Capture the Current State and Update the Heatmap
# ------------------------------------------------------------------------------
@app.callback(
    Output("heatmap", "figure"),
    [Input("interval", "n_intervals")]
)
def update_heatmap(n):
    global snapshot_id, historical_data, current_order_book

    snapshot_id += 1
    global trade_price_history

    if last_trade_price is not None:
        trade_price_history.append((snapshot_id, last_trade_price))

    # Limit history to match heatmap range
    if len(trade_price_history) > 5000:
        trade_price_history = trade_price_history[-5000:]

    if not current_order_book:
        return go.Figure().update_layout(
            title="Waiting for order book data...",
            xaxis_title="Snapshot Index",
            yaxis_title="Binned Price",
            height=600
        )

    # Create snapshot from current order book state
    snapshot_rows = [
        {
            "snapshot_id": snapshot_id,
            "side": side,
            "price": float(price),
            "qty": float(qty)
        }
        for (side, price), qty in current_order_book.items()
    ]
    df_snapshot = pd.DataFrame(snapshot_rows)

    bids = df_snapshot[df_snapshot["side"] == "bid"].copy()
    asks = df_snapshot[df_snapshot["side"] == "ask"].copy()

    bids = bids.sort_values(by="price", ascending=False)
    bids["cum_qty"] = bids["qty"].cumsum()

    asks = asks.sort_values(by="price", ascending=True)
    asks["cum_qty"] = asks["qty"].cumsum()

    df_cumulative = pd.concat([bids, asks], ignore_index=True)
    df_cumulative["snapshot_id"] = snapshot_id

    if df_snapshot.empty:
        return go.Figure().update_layout(
            title="Order book temporarily empty",
            xaxis_title="Snapshot Index",
            yaxis_title="Binned Price",
            height=600
        )

    # Accumulate over time
    global historical_data
    historical_data = pd.concat([historical_data, df_cumulative], ignore_index=True)

    # Optional trimming
    if snapshot_id > 5000:
        historical_data = historical_data[historical_data["snapshot_id"] > snapshot_id - 5000]

    # Create pivot: price x snapshot_id with cumulative volume as value
    pivot = historical_data.pivot_table(
        index="price",
        columns="snapshot_id",
        values="cum_qty",  # 🔥 use cumulative quantity
        aggfunc="max",     # Only one value per (price, snapshot), but max is safe
        fill_value=0)

    # Get price range to reverse Y-axis
    if not pivot.empty:
        prices = list(pivot.index)
        y_range = [max(prices), min(prices)]
    else:
        y_range = None

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale="Viridis",
        colorbar=dict(title="Cumulative Qty")
    ))

    
    # Overlay trade price history as a line
    if trade_price_history:
        trade_df = pd.DataFrame(trade_price_history, columns=["snapshot_id", "price"])

        fig.add_trace(go.Scatter(
            x=trade_df["snapshot_id"],
            y=trade_df["price"],
            mode="lines+markers",
            name="Last Trade Price",
            line=dict(color="orange", width=2),
            marker=dict(size=6, color="orange", symbol="circle"),
            yaxis="y"
        ))
    # ✅ Force y-axis to show low → high (bottom to top)
    fig.update_layout(
        title="BTC/USD Order Book Depth (Real-Time)",
        xaxis_title="Snapshot Index (Time)",
        yaxis=dict(
            title="Binned Price",
            autorange=True  # ✅ This is key: do NOT reverse it manually
        ),
            font=dict(
        size=24  # Change this value as needed
        ),
        height=1500,
        hoverlabel=dict(
            font_size=24  # or whatever size you prefer
    )
    )

    return fig


# ------------------------------------------------------------------------------
# Run the Dash App
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
