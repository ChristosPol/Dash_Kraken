# Import packages
from dash import Dash, html, dash_table, dcc, callback, Output, Input
import pandas as pd
import plotly.express as px
import sys
import json
import signal
import time
import pandas as pd
import websocket
import numpy as np
from sty import fg, bg, ef, rs
from datetime import datetime


# Initialize the app
app = Dash()



# Run the app
if __name__ == '__main__':
    app.run(debug=True)