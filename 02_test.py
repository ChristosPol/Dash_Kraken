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
import numpy as np

pair = ["BTC/USD"]

prices = []
quantities=[]
sides=[]
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

window_size=1000

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
    global prices, sell_volumes_vec, buy_volumes_vec, sell_trades_vec, buy_trades_vec, sides, quantities
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
            quantities.append(qty)
            sides.append(side)

            # Update volumes and trades based on side
            if side == "sell":
                qty = data[x]["qty"]
                sell_volumes_vec.append(qty)
                buy_volumes_vec.append(0)
                buy_trades_vec.append(0)
                sell_trades_vec.append(1)
                
            else:
                qty = data[x]["qty"]
                buy_volumes_vec.append(qty)
                sell_volumes_vec.append(0)
                buy_trades_vec.append(1)
                sell_trades_vec.append(0)


def tail_cumsum(vec, window_size):
    if len(vec) > window_size:
        return np.cumsum(vec)[-window_size:]  # Get cumulative sum for the last `window_size` values
    else:
        return np.cumsum(vec) 
    

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
        
        html.Div(
    style={
        'display': 'flex',
        'flexDirection': 'row',
        'justifyContent': 'center',
        'gap': '20px',
        'flex': 1,
        'padding': '10px'
    },
    children=[
        # Left Column
        html.Div(
            style={
                'display': 'flex',
                'flexDirection': 'column',
                'gap': '10px',
                'flex': 1
            },
            children=[
                dcc.Graph(id='price-graph', style={'flex': 1, 'width': '100%', 'height': 'auto'}, config={'displayModeBar': False}),
                dcc.Graph(id='volume-graph', style={'flex': 1, 'width': '100%', 'height': 'auto'}, config={'displayModeBar': False}),
                dcc.Graph(id='trade-graph', style={'flex': 1, 'width': '100%', 'height': 'auto'}, config={'displayModeBar': False})
            ]
        ),

        # Right Column
        html.Div(
            style={
                'display': 'flex',
                'flexDirection': 'column',
                'gap': '10px',
                'flex': 1
            },
            children=[
                dcc.Graph(id='colourful_price_ind', config={'displayModeBar': False}, style={'height': '33%'}),
                dcc.Graph(id='colourful_volume_ind', config={'displayModeBar': False}, style={'height': '33%'})
            ]
        )
    ]
),
        dcc.Interval(id='interval-component', interval=250, n_intervals=0)
    ]
)

@app.callback(
    [Output('price-graph', 'figure'),
     Output('volume-graph', 'figure'),
     Output('trade-graph', 'figure'),
     Output('colourful_price_ind', 'figure'),
     Output('colourful_volume_ind', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_graphs(n):
    # Ensure we have some data to display
    if len(prices) == 0:
        return go.Figure(), go.Figure(), go.Figure(), go.Figure(), go.Figure()

    # PRICE PLOT ---------------------------------
    price_fig = go.Figure()
    price_fig.add_trace(go.Scatter(
        y=prices[-window_size:],  # Use the 'prices' list (not the undefined 'price')
        mode='lines',
        name='Price',
        line=dict(color='lightgreen'))
    )
    price_fig.update_layout(
        margin=dict(l=70, r=10, t=2, b=2),
        height=250,
        yaxis=dict(visible=True, tickfont=dict(color='white')),
        xaxis=dict(tickfont=dict(color='white')),
        plot_bgcolor='#3d3a3a',  # Change background color of the plot to black
        paper_bgcolor='#3d3a3a'
    )

    # VOLUME CUMSUM PLOT ---------------------------------
    volume_fig = go.Figure()
    buy_vol_cumsum = tail_cumsum(buy_volumes_vec, window_size)
    sell_vol_cumsum = tail_cumsum(sell_volumes_vec, window_size)

    volume_fig.add_trace(go.Scatter(
        y=buy_vol_cumsum,
        mode='lines',
        name='Buy Volume Cumsum',
        line=dict(color='green')
    ))
    volume_fig.add_trace(go.Scatter(
        y=sell_vol_cumsum,
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

    # TRADES CUMSUM PLOT ---------------------------------
    trades_fig = go.Figure()
    
    buy_trd_cumsum = tail_cumsum(buy_trades_vec, window_size)
    sell_trd_cumsum = tail_cumsum(sell_trades_vec, window_size)

    if buy_trades_vec:
        trades_fig.add_trace(go.Scatter(
            x=list(range(len(buy_trd_cumsum))),
            y=buy_trd_cumsum,
            mode='lines',
            name='Buy Trades Cumsum',
            line=dict(color='green')
        ))

    if sell_trades_vec:
        trades_fig.add_trace(go.Scatter(
            x=list(range(len(sell_trd_cumsum))),
            y=sell_trd_cumsum,
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
    

    # PRICE W/ COLOURED MARKERS ---------------------------------
    col_price_fig = go.Figure()

    # Only use latest `window_size` points
    x_vals = list(range(len(prices[-window_size:])))
    colors = ['green' if side == 'buy' else 'red' for side in sides[-window_size:]]

    col_price_fig.add_trace(go.Scatter(
        x=x_vals,
        y=prices[-window_size:],
        mode='markers',
        marker=dict(color=colors),
        name='Price (Coloured)'
    ))

    col_price_fig.update_layout(
        margin=dict(l=70, r=10, t=2, b=2),
        height=250,
        yaxis=dict(visible=True, tickfont=dict(color='white')),
        xaxis=dict(tickfont=dict(color='white')),
        plot_bgcolor='#3d3a3a',
        paper_bgcolor='#3d3a3a'
    )
    
    # VOLUME BARPLOT ---------------------------------
    volume_bar_fig = go.Figure()

    bar_colors = ['green' if side == 'buy' else 'red' for side in sides[-window_size:]]
    x_vals = list(range(len(quantities[-window_size:])))

    volume_bar_fig.add_trace(go.Bar(
        x=x_vals,
        y=quantities[-window_size:],
        marker_color=bar_colors,
        name='Volume'
    ))

    volume_bar_fig.update_layout(
        margin=dict(l=70, r=10, t=2, b=2),
        height=250,
        yaxis=dict(visible=True, tickfont=dict(color='white')),
        xaxis=dict(tickfont=dict(color='white')),
        plot_bgcolor='#3d3a3a',
        paper_bgcolor='#3d3a3a'
    )

    return price_fig, volume_fig, trades_fig, col_price_fig, volume_bar_fig


if __name__ == '__main__':
    app.run(debug=True)
