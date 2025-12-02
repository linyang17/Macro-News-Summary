import time
import schedule
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()


# ================= MODULES =================
from config import OPENAI_API_KEY, LANGUAGE_MODE
from markets import get_market_snapshot
from mktsource import fetch_news
from analysis import analyse_market
from notification import send_msg_slack

# ================= MAIN LOGIC =================
def job():
    print(f"Starting job at {datetime.now()}...")
    
    # 1. Get Data
    mkt_data = get_market_snapshot()
    news_data = fetch_news()
    
    # 2. Analyze
    client = OpenAI(api_key=OPENAI_API_KEY)
    report = analyse_market(client, mkt_data, news_data, LANGUAGE_MODE)
    
    # 3. Send
    final_output = f"📅 Global Macro Brief | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{report}"
    send_msg_slack(final_output)

if __name__ == "__main__":
    # Schedule setup
    schedule.every().day.at("07:00").do(job)
    schedule.every().day.at("12:00").do(job)
    schedule.every().day.at("16:00").do(job)
    schedule.every().day.at("21:00").do(job)
    
    print("System initialized. Waiting for schedule...")
    while True:
        schedule.run_pending()
        time.sleep(60)

# ================= GCP HTTP ENTRYPOINT =================
def run_news(request):
    """
    HTTP entrypoint for Cloud Run Function.
    Calling this URL runs a single newsletter job and returns simple text.
    """
    print("GCP run_news triggered")
    job()
    return "OK"