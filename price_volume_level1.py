import json
import signal
import time
import pandas as pd
import websocket
import numpy as np
from sty import fg, bg, ef, rs
from datetime import datetime
from itertools import accumulate
import threading
import dash
from dash import dcc, html, Dash
from dash.dependencies import Input, Output
import plotly.graph_objs as go

pair = ["BTC/USD"]

prices = []
buy_volumes = []
sell_volumes = []
buy_trades = []
sell_trades = []

buy_vol_cum = 0
sell_vol_cum = 0
buy_trd_cum = 0
sell_trd_cum = 0

buy_volumes_vec = []
sell_volumes_vec = []
buy_trades_vec = []
sell_trades_vec = []


message = {
    "method": "subscribe",
    "params": {
        "symbol": pair,
        "channel": "trade"
    }
}
message_ready = json.dumps(message)


def ws_open(ws):
    print("✅ WebSocket connection opened.")
    ws.send(message_ready)


def ws_message(ws, message):
    global prices, sell_volumes_vec, buy_volumes_vec, sell_trades_vec, buy_trades_vec, buy_vol_cum, sell_vol_cum, buy_trd_cum, sell_trd_cum
    api_data = json.loads(message)
    if len(api_data) > 2:
        data = api_data['data']
        n_tr = len(data)
        
        for x in range(n_tr):
            price = data[x]["price"]
            qty = data[x]["qty"]
            side = data[x]["side"]

            # Update prices
            prices.append(price)

            # Update volumes and trades based on side
            if side == "sell":
                sell_volumes.append(qty)
                buy_volumes.append(0)
                sell_trades.append(1)
                buy_trades.append(0)
                sell_vol_cum += qty
                sell_trd_cum += 1
            else:
                buy_volumes.append(qty)
                sell_volumes.append(0)
                buy_trades.append(1)
                sell_trades.append(0)
                buy_vol_cum += qty
                buy_trd_cum += 1

            # Append cumulative volumes and trades to vectors
            buy_volumes_vec.append(buy_vol_cum)
            sell_volumes_vec.append(sell_vol_cum)
            buy_trades_vec.append(buy_trd_cum)
            sell_trades_vec.append(sell_trd_cum)


def run_websocket():
    ws = websocket.WebSocketApp('wss://ws.kraken.com/v2', on_open=ws_open, on_message=ws_message)
    ws.run_forever()


ws_thread = threading.Thread(target=run_websocket, daemon=False)
ws_thread.start()

app = Dash()

app.layout = html.Div(
    style={
        'display': 'flex',
        'flexDirection': 'column',
        'height': '100vh',
        'padding': '0',
        'margin': '0',
        'gap': '0px',  # controls spacing between graphs
        'overflow': 'hidden',
        'backgroundColor': '#3d3a3a'
    },
    children=[
        html.H4("Live BTC/USD Data", style={
            "textAlign": "center",
            "color": "white"
        }),
        dcc.Graph(id='price-graph', style={'flex': 1, 'width': '50vw', 'height': 'auto'}, config={'displayModeBar': False}),
        dcc.Graph(id='volume-graph', style={'flex': 1, 'width': '50vw', 'height': 'auto'}, config={'displayModeBar': False}),
        dcc.Graph(id='trade-graph', style={'flex': 1, 'width': '50vw', 'height': 'auto'}, config={'displayModeBar': False}),
        dcc.Interval(id='interval-component', interval=250, n_intervals=0)
    ]
)


@app.callback(
    [Output('price-graph', 'figure'),
     Output('volume-graph', 'figure'),
     Output('trade-graph', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_graphs(n):
    # Ensure we have some data to display
    if len(prices) == 0:
        return go.Figure(), go.Figure(), go.Figure()

    # PRICE PLOT
    price_fig = go.Figure()
    price_fig.add_trace(go.Scatter(
        y=prices,  # Use the 'prices' list (not the undefined 'price')
        mode='lines',
        name='Price',
        line=dict(color='lightgreen')
    ))
    price_fig.update_layout(
        margin=dict(l=70, r=10, t=2, b=2),
        height=250,
        yaxis=dict(visible=True, tickfont=dict(color='white')),
        xaxis=dict(tickfont=dict(color='white')),
        plot_bgcolor='#3d3a3a',  # Change background color of the plot to black
        paper_bgcolor='#3d3a3a'
    )

    # VOLUME CUMSUM PLOT
    volume_fig = go.Figure()
    volume_fig.add_trace(go.Scatter(
        y=buy_volumes_vec,
        mode='lines',
        name='Buy Volume Cumsum',
        line=dict(color='green')
    ))
    volume_fig.add_trace(go.Scatter(
        y=sell_volumes_vec,
        mode='lines',
        name='Sell Volume Cumsum',
        line=dict(color='red')
    ))
    volume_fig.update_layout(
        showlegend=False,
        margin=dict(l=70, r=10, t=2, b=2),
        height=250,
        yaxis=dict(visible=True, tickfont=dict(color='white')),
        xaxis=dict(tickfont=dict(color='white')),
        plot_bgcolor='#3d3a3a',  # Change background color of the plot to black
        paper_bgcolor='#3d3a3a'
    )

    # TRADES CUMSUM PLOT
    trades_fig = go.Figure()

    if buy_trades_vec:
        trades_fig.add_trace(go.Scatter(
            x=list(range(len(buy_trades_vec))),
            y=buy_trades_vec,
            mode='lines',
            name='Buy Trades Cumsum',
            line=dict(color='green')
        ))

    if sell_trades_vec:
        trades_fig.add_trace(go.Scatter(
            x=list(range(len(sell_trades_vec))),
            y=sell_trades_vec,
            mode='lines',
            name='Sell Trades Cumsum',
            line=dict(color='red')
        ))

    trades_fig.update_layout(
        showlegend=False,
        margin=dict(l=70, r=10, t=2, b=2),
        height=250,
        yaxis=dict(visible=True, tickfont=dict(color='white')),
        xaxis=dict(tickfont=dict(color='white')),
        plot_bgcolor='#3d3a3a',
        paper_bgcolor='#3d3a3a'
    )

    return price_fig, volume_fig, trades_fig


if __name__ == '__main__':
    app.run(debug=True)
