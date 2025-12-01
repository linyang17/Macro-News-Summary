from flask import Flask
from main import job

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def run_news():
    print("Cloud Run: run_news triggered")
    job() 
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)