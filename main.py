import os
import time
import schedule
import yfinance as yf
import requests
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# ================= CONFIGURATION =================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWSAPI_KEY = os.getenv("NEWS_API_KEY") # https://newsapi.org/
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY") # https://finnhub.io/
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # Slack/Feishu webhook
LANGUAGE_MODE = os.getenv("LANGUAGE_MODE", "MIXED") # EN, CN, MIXED

client = OpenAI(api_key=OPENAI_API_KEY)

# ================= MARKET DATA MODULE =================
def get_market_snapshot():
    tickers = {
        "FX": ["EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "CNY=X"], # CNY=X is USDCNY
        "RATES": ["^TNX", "^FVX", "^IRX"], # 10Y, 5Y, 13-Week (Proxy for short term)
        "COMMO": ["GC=F", "CL=F"], # Gold, Crude Oil
        "INDEX": ["^GSPC", "^IXIC", "^HSI"], # SPX, Nasdaq, Hang Seng
        "VIX": ["^VIX"]
    }
    
    data_str = "【Market Snapshot】\n"
    
    # Batch fetch for efficiency
    all_tickers = [item for sublist in tickers.values() for item in sublist]
    tickers_data = yf.Tickers(" ".join(all_tickers))
    
    for category, symbols in tickers.items():
        data_str += f"[{category}]\n"
        for sym in symbols:
            try:
                info = tickers_data.tickers[sym].fast_info
                price = info.last_price
                prev_close = info.previous_close
                change_pct = ((price - prev_close) / prev_close) * 100
                
                # Format name mapping
                name = sym.replace("=X", "").replace("=F", "").replace("^", "")
                if sym == "CNY=X": name = "USDCNY"
                if sym == "^TNX": name = "US10Y"
                if sym == "^FVX": name = "US05Y"
                
                emoji = "🟢" if change_pct > 0 else "🔴"
                data_str += f" {name}: {price:.4f} {emoji}  ({change_pct:+.2f}%)\n"
            except:
                continue
        data_str += "------------------\n"
    
    return data_str

# ================= NEWS AGGREGATOR MODULE =================
def fetch_news():
    news_items = []
    
    # Source 1: Yahoo Finance (Via yfinance - excellent for free macro news)
    try:
        # Looking at broad macro tickers
        macro_tickers = yf.Tickers("EURUSD=X ^GSPC ^TNX")
        for ticker in ["EURUSD=X", "^GSPC", "^TNX"]:
            news = macro_tickers.tickers[ticker].news
            for n in news[:3]: # Top 3 per ticker
                news_items.append(f"Source: Yahoo | Title: {n['title']}")
    except Exception as e:
        print(f"Yahoo News Error: {e}")

    # Source 2: Finnhub (Market News)
    if FINNHUB_KEY:
        try:
            url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}"
            r = requests.get(url).json()
            for n in r[:5]:
                news_items.append(f"Source: Finnhub | Title: {n['headline']} | Summary: {n['summary']}")
        except Exception as e:
            print(f"Finnhub Error: {e}")

    # Source 3: NewsAPI (Global Macro)
    if NEWSAPI_KEY:
        try:
            url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWSAPI_KEY}"
            r = requests.get(url).json()
            if 'articles' in r:
                for n in r['articles'][:5]:
                    news_items.append(f"Source: NewsAPI | Title: {n['title']}")
        except Exception as e:
            print(f"NewsAPI Error: {e}")

    return "\n".join(news_items)

# ================= MD ANALYST (LLM) MODULE =================
def analyze_market(market_data, raw_news):
    
    system_prompt = """
    You are a Global Macro Strategist at a top-tier Investment Bank (FICC Desk). 
    Your audience consists of professional Rates, FX, and Treasury traders.
    
    Your goal: Synthesize market data and news into a high-signal, professional briefing.
    
    Requirements:
    1. Tone: Professional, direct, 'Traders' Talk'. No fluff.
    2. Focus: Central Bank Policy (Fed/ECB/BOE/BOJ/PBOC etc), Geopolitics affecting supply chains/energy, Yield Curve dynamics, FX Flows.
    3. Structure:
       - Market Levels (Keep it brief)
       - The Narrative (Deep logic analysis: Why are things moving? Connection between rates/FX/Commodities)
       - Watchlist (What to look for next)
    """
    
    if LANGUAGE_MODE == "MIXED":
        lang_instruction = """
        Output Language: 'Chinglish' (Chinese grammar with professional English Terminology).
        Example: "US 10Y Yield 突破关键节点，预示市场正在 re-price 年底前 Fed 再加息一次的概率。如果 PCE 数据超预期，VIX 可能会 spike 到 25 以上，此时 risk-off sentiment 将主导 Cross-asset correlation，建议减少 equity exposure，在此位置 long USDCNY 依然是 carry 和 hedge 的较好选择。"
        Use English for: Financial terms (Duration, Convexity, Bear Steepening, Pivot), some Action verbs (Re-price, Rally, Sell-off), Asset classes.
        """
    elif LANGUAGE_MODE == "EN":
        lang_instruction = "Output Language: Professional English."
    else:
        lang_instruction = "Output Language: Professional Chinese."

    user_content = f"""
    Current Time: {datetime.now()}
    
    [Market Data Snapshot]
    {market_data}
    
    [Raw News Feed]
    {raw_news}
    
    Please write the analysis now.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-5.1", # Use latest model for analysis
            messages=[
                {"role": "system", "content": system_prompt + lang_instruction},
                {"role": "user", "content": user_content}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating analysis: {e}"

# ================= NOTIFICATION MODULE =================
def send_notification(content):
    if not WEBHOOK_URL:
        print("No Webhook URL set. Printing to console.")
        print(content)
        return

    # Adapting for Feishu/Lark (JSON format)
    # If using Slack, change payload structure accordingly
    payload = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }
    
    try:
        requests.post(WEBHOOK_URL, json=payload)
        print("Notification sent.")
    except Exception as e:
        print(f"Notification Failed: {e}")

# ================= MAIN LOGIC =================
def job():
    print(f"Starting job at {datetime.now()}...")
    
    # 1. Get Data
    mkt_data = get_market_snapshot()
    news_data = fetch_news()
    
    # 2. Analyze
    report = analyze_market(mkt_data, news_data)
    
    # 3. Send
    final_output = f"📅 Global Macro Brief | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{report}"
    send_notification(final_output)

if __name__ == "__main__":
    # Schedule setup
    schedule.every().day.at("07:00").do(job)
    schedule.every().day.at("12:00").do(job)
    schedule.every().day.at("16:00").do(job)
    schedule.every().day.at("21:00").do(job)
    
    # Run once immediately for testing/debugging (optional, remove in prod)
    # job() 
    
    print("System initialized. Waiting for schedule...")
    while True:
        schedule.run_pending()
        time.sleep(60)