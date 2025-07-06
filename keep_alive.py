from flask import Flask
from threading import Thread
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "Wordle Solver Bot is alive!"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": time.time()}

def run():
    app.run(host='0.0.0.0', port=5000, debug=False)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
