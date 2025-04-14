from dash import Dash, html

app = Dash() # Initialize the app

# Requires Dash 2.17.0 or later
app.layout = [html.Div(children='Hello World')]

if __name__ == '__main__':
    app.run(debug=True)