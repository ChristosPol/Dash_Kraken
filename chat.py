import pandas as pd
import json
import threading
import math
import websocket
import numpy as np
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go

# ------------------------------------------------------------------------------
# Global Variables & Parameters
# ------------------------------------------------------------------------------
current_order_book = {}
historical_data = pd.DataFrame(columns=["snapshot_id", "side", "price", "qty"])
snapshot_id = 0
last_trade_price = None
PRICE_INCREMENT = 1
trade_price_history = []  # (snapshot_id, price, side, qty)

# ------------------------------------------------------------------------------
# Helper Function to Bin Prices
# ------------------------------------------------------------------------------
def bin_price(price, increment):
    return math.floor(price / increment) * increment

# ------------------------------------------------------------------------------
# WebSocket Subscription Messages
# ------------------------------------------------------------------------------
book_message = {
    "method": "subscribe",
    "params": {
        "channel": "book",
        "symbol": ["BTC/USD"],
        "depth": 100,
        "snapshot": True
    }
}
trades_message = {
    "method": "subscribe",
    "params": {
        "symbol": ["BTC/USD"],
        "channel": "trade"
    }
}
message_ready = json.dumps(book_message)
message_ready_trades = json.dumps(trades_message)

# ------------------------------------------------------------------------------
# WebSocket Handlers
# ------------------------------------------------------------------------------
def ws_open(ws):
    print("✅ WebSocket connection opened.")
    ws.send(message_ready)
    ws.send(message_ready_trades)

def on_message(ws, message):
    global current_order_book, last_trade_price, trade_price_history, snapshot_id

    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        print("❌ Failed to decode message")
        return

    if isinstance(data, dict) and data.get("channel") == "trade":
        trades = data.get("data", [])
        if trades:
            trade = trades[-1]
            price = float(trade.get("price"))
            qty = float(trade.get("qty", 1))
            side = trade.get("side", "buy")
            last_trade_price = price
            trade_price_history.append((snapshot_id, price, side, qty))
            print(f"💰 Trade: {side.upper()} @ {price} ({qty})")
        return

    if isinstance(data, dict) and data.get("channel") == "book":
        msg_type = data.get("type")
        updates = data.get("data", [])

        if not updates:
            return

        update = updates[0]
        bids = update.get("bids", [])
        asks = update.get("asks", [])

        if msg_type == "snapshot":
            current_order_book.clear()
            print("📸 Full snapshot received")

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
# Start WebSocket Thread
# ------------------------------------------------------------------------------
ws_thread_book = threading.Thread(target=run_websocket_book, daemon=True)
ws_thread_book.start()

# ------------------------------------------------------------------------------
# Dash App Layout
# ------------------------------------------------------------------------------
app = Dash(__name__)

app.layout = html.Div([
    html.H2("Kraken SOL/USD Order Book Depth Heatmap (Real-Time)"),
    dcc.Graph(id="heatmap"),
    dcc.Interval(id="interval", interval=1000, n_intervals=0)
])

# ------------------------------------------------------------------------------
# Dash Callback for Heatmap Updates
# ------------------------------------------------------------------------------
@app.callback(
    Output("heatmap", "figure"),
    [Input("interval", "n_intervals")]
)
def update_heatmap(n):
    global snapshot_id, historical_data, current_order_book, trade_price_history

    snapshot_id += 1

    if not current_order_book:
        return go.Figure().update_layout(
            title="Waiting for order book data...",
            xaxis_title="Snapshot Index",
            yaxis_title="Binned Price",
            height=600
        )

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

    bids = df_snapshot[df_snapshot["side"] == "bid"].sort_values(by="price", ascending=False)
    asks = df_snapshot[df_snapshot["side"] == "ask"].sort_values(by="price", ascending=True)

    bids["cum_qty"] = bids["qty"].cumsum()
    asks["cum_qty"] = asks["qty"].cumsum()

    df_cumulative = pd.concat([bids, asks], ignore_index=True)
    df_cumulative["snapshot_id"] = snapshot_id

    historical_data = pd.concat([historical_data, df_cumulative], ignore_index=True)

    if snapshot_id > 5000:
        historical_data = historical_data[historical_data["snapshot_id"] > snapshot_id - 5000]
        trade_price_history = [t for t in trade_price_history if t[0] > snapshot_id - 5000]

    pivot = historical_data.pivot_table(
        index="price",
        columns="snapshot_id",
        values="cum_qty",
        aggfunc="max",
        fill_value=0)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale="Viridis",
        colorbar=dict(title="Cumulative Qty")
    ))

    # Plot trades as points with adaptive size and color
    if trade_price_history:
        trade_df = pd.DataFrame(trade_price_history, columns=["snapshot_id", "price", "side", "qty"])
        trade_df["color"] = trade_df["side"].map({"buy": "green", "sell": "red"})

        # Adaptive marker size using percentiles
        q_05 = trade_df["qty"].quantile(0.05)
        q_95 = trade_df["qty"].quantile(0.95)
        trade_df["size"] = trade_df["qty"].apply(
            lambda x: 8 + 22 * min(1, max(0, (x - q_05) / (q_95 - q_05)))
        )

        fig.add_trace(go.Scatter(
            x=trade_df["snapshot_id"],
            y=trade_df["price"],
            mode="markers",
            name="Trades",
            customdata=trade_df[["qty", "side"]],
            marker=dict(
                size=trade_df["size"],
                color=trade_df["color"],
                symbol="circle",
                opacity=0.8,
                line=dict(width=1, color=trade_df["color"])  # matching outline color
            ),
            hovertemplate="Snapshot: %{x}<br>Price: %{y}<br>Side: %{customdata[1]}<br>Qty: %{customdata[0]:.2f}<extra></extra>"
        ))

    fig.update_layout(
        title="SOL/USD Order Book Depth (Real-Time)",
        xaxis_title="Snapshot Index (Time)",
        yaxis=dict(
            title="Binned Price",
            autorange=True
        ),
        font=dict(size=14),
        legend=dict(font=dict(size=14)),
        hoverlabel=dict(font_size=16),
        height=1500
    )

    return fig

# ------------------------------------------------------------------------------
# Run Dash Server
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
