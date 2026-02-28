import json
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

DATA_FILE = "data/signals_2026.json"

app = FastAPI()

def load_signals():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def generate_bluesky_post(player):
    return f"""{player} spring signal update:

Raw EV Δ: {player['raw_delta_EV']:.2f} mph
Bias-adjusted Δ: {player['adjusted_delta_EV']:.2f} mph
Confidence index: {player['confidence_index']:.2f}

#Orioles #Birdland"""

@app.get("/", response_class=HTMLResponse)
def home():

    signals = load_signals()

    rows = ""
    for p in sorted(signals, key=lambda x: x["confidence_index"], reverse=True):
        rows += f"""
        <tr>
            <td>{p['player']}</td>
            <td>{p['raw_delta_EV']:.2f}</td>
            <td>{p['adjusted_delta_EV']:.2f}</td>
            <td>{p['confidence_index']:.2f}</td>
            <td>
                <button onclick="copyPost('{generate_bluesky_post(p).replace(chr(10), ' ')}')">
                    Copy BlueSky
                </button>
            </td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                background: #0f172a;
                color: white;
                font-family: -apple-system;
                padding: 20px;
            }}
            h1 {{
                color: #df4a00;
            }}
            table {{
                width: 100%;
                font-size: 14px;
            }}
            th, td {{
                padding: 8px;
            }}
            button {{
                background: #df4a00;
                border: none;
                padding: 6px 10px;
                color: white;
                border-radius: 6px;
            }}
        </style>
        <script>
            function copyPost(text) {{
                navigator.clipboard.writeText(text);
                alert("Copied to clipboard!");
            }}
        </script>
    </head>
    <body>
        <h1>🟠 BirdlandMetrics Spring Signal</h1>
        <table>
            <tr>
                <th>Player</th>
                <th>Raw EV Δ</th>
                <th>Adj EV Δ</th>
                <th>Confidence</th>
                <th>BlueSky</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """

    return html
