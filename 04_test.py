import pandas as pd
import time
import json
import threading
from datetime import datetime
import websocket
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
PRICE_INCREMENT = 100

current_order_book = {}  # keys: tuple like ("bid", 84800) or ("ask", 84900)
# Historical record of snapshots (each row records a snapshot of the current state)
historical_data = pd.DataFrame(columns=["snapshot_id", "side", "price", "qty"])
# Counter for snapshots (each Dash timer tick increases it)
snapshot_id = 0
# ------------------------------------------------------------------------------
# Helper Function to Bin Prices
# ------------------------------------------------------------------------------
def bin_price(price, increment):
    """
    Floors the price to the lower increment.
    Example: if price = 84855 and increment = 100, returns 84800.
    """
    return math.floor(price / increment) * increment
book_message = {
        "method": "subscribe",
        "params": {
            "channel": "book",
            "symbol": ["BTC/USD"],
            "depth": 100,
            "snapshot": True
        }
}
message_ready = json.dumps(book_message)

def ws_open(ws):
    print("✅ WebSocket connection opened.")
    ws.send(message_ready)


order_book_data = {
    "bids": pd.DataFrame(columns=["price", "volume"]),
    "asks": pd.DataFrame(columns=["price", "volume"])
}

def on_message(ws, message):
    global order_book_data, df_update
    

    data = json.loads(message)
    
    if data['channel'] =="book":
        #time=datetime.now().strftime('%H:%M:%S')
        if data['type'] =="snapshot":
            bids = data['data'][0]['bids']
            asks = data['data'][0]['asks']
            df_bids = pd.DataFrame(bids)
            df_bids['side'] = 'bid'
            df_asks = pd.DataFrame(asks)
            df_asks['side'] = 'ask'
            # Combine them
            df_snapshot = pd.concat([df_bids, df_asks], ignore_index=True)
            

        if data['type'] == 'update':
            bids = data['data'][0]['bids']
            asks = data['data'][0]['asks']
            df_bids = pd.DataFrame(bids)
            df_bids['side'] = 'bid'
            df_asks = pd.DataFrame(asks)
            df_asks['side'] = 'ask'
            # Combine them
            df_update = pd.concat([df_bids, df_asks], ignore_index=True)

        df_update=pd.concat([df_snapshot, df_update], ignore_index=True)

    


def on_error(ws, error):
    print("❌ WebSocket Error:", error)

def on_close(ws, code, msg):
    print(f"🔌 WebSocket closed. Code: {code}, Reason: {msg}")

def run_websocket_book():
    ws = websocket.WebSocketApp(
        'wss://ws.kraken.com/v2',
        on_open=ws_open,
        on_message=on_message,
        #on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# Start WebSocket in a separate thread
ws_thread_book = threading.Thread(target=run_websocket_book, daemon=False)
ws_thread_book.start()


# app = Dash()

# app.layout = html.Div([
#     html.H2("Kraken Order Book Heatmap (BTC/USD)"),
#     dcc.Graph(id="heatmap"),
#     dcc.Interval(id="interval", interval=1000, n_intervals=0)  # Update every 1s
# ])

# @app.callback(
#     Output("heatmap", "figure"),
#     Input("interval", "n_intervals")
# )
# def update_heatmap(n):
#     global df_update

#     if df_update.empty:
#         fig = go.Figure(data=go.Heatmap(z=[[0]]))
#         fig.update_layout(title='No data yet')
#         return fig

#     df = df_update.copy()
#     df['timestamp'] = pd.to_datetime('now').round('s')
#     df['price'] = df['price'].astype(float).round(0)

#     # Pivot table: timestamps (rows), prices (columns), sum(qty) as values
#     pivot = df.groupby(['timestamp', 'price'])['qty'].sum().unstack(fill_value=0)

#     fig = go.Figure(data=go.Heatmap(
#         z=pivot.values.T,  # transpose so time is x-axis
#         x=pivot.index.astype(str),  # convert timestamps to strings
#         y=pivot.columns,
#         colorscale='Viridis',
#         colorbar=dict(title='Qty')
#     ))

#     fig.update_layout(
#         title='BTC/USD Order Book Heatmap',
#         xaxis_title='Time',
#         yaxis_title='Price',
#         height=600
#     )

#     return fig



# if __name__ == "__main__":
#     app.run(debug=True)