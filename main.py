import os
import time
import schedule
import yfinance as yf
import requests
import json
from datetime import datetime, timezone
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()


# ================= CONFIGURATION =================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWSAPI_KEY = os.getenv("NEWS_API_KEY") # https://newsapi.org/
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY") # https://finnhub.io/
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL") # Slack webhook
LANGUAGE_MODE = os.getenv("LANGUAGE_MODE", "MIXED") # EN, CN, MIXED

client = OpenAI(api_key=OPENAI_API_KEY)


# ================= MARKET OF INTEREST =================
# Shared tickers universe for both market snapshot and news fetching
MARKET_TICKERS = {
    "FX": ["EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "CNY=X"],  # CNY=X is USDCNY
    "RATES": ["^TNX", "^FVX", "^IRX"],  # 10Y, 5Y, 13-Week (Proxy for short term)
    "COMMO": ["GC=F", "CL=F"],  # Gold, Crude Oil
    "INDEX": ["^GSPC", "^IXIC", "^HSI"],  # SPX, Nasdaq, Hang Seng
    "VIX": ["^VIX"],
}

# ================= MARKET DATA MODULE =================
def get_market_snapshot():
    
    tickers = MARKET_TICKERS

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
    """
    Fetch today's macro news (from 00:00 UTC to now) from multiple sources.
    Returns a single string containing each news item on its own line and
    prints the total number of news items fetched.
    """
    news_items: list[str] = []

    # Define 'today' range in UTC
    now_utc = datetime.now(timezone.utc)
    start_of_day_utc = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)

    # Source 1: Yahoo Finance
    try:
        # Use ALL tickers defined in MARKET_TICKERS (no manual subset)
        all_symbols = [sym for symbols in MARKET_TICKERS.values() for sym in symbols]
        macro_tickers = yf.Tickers(" ".join(all_symbols))
        for ticker in all_symbols:
            yf_ticker = macro_tickers.tickers.get(ticker)
            if yf_ticker is None:
                continue
            news_list = getattr(yf_ticker, "news", []) or []

            for item in news_list:
                # providerPublishTime is a UNIX timestamp (seconds)
                ts = item.get("providerPublishTime")
                if not ts:
                    continue
                published_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                # Only keep news from today (UTC)
                if published_dt < start_of_day_utc or published_dt > now_utc:
                    continue

                title = item.get("title") or ""
                summary = item.get("summary") or ""
                source = item.get("publisher") or "Yahoo Finance"

                line_parts = [
                    f"Source: {source}",
                    f"Section: Yahoo-{ticker}",
                ]
                if title:
                    line_parts.append(f"Title: {title}")
                if summary:
                    line_parts.append(f"Summary: {summary}")
                news_items.append(" | ".join(line_parts))
    except Exception as e:
        print(f"Yahoo News Error: {e}")

    # Source 2: Finnhub (General Market News)
    if FINNHUB_KEY:
        try:
            url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}"
            res = requests.get(url)
            data = res.json() if hasattr(res, "json") else []
            if isinstance(data, list):
                for item in data:
                    ts = item.get("datetime")
                    if not ts:
                        continue
                    published_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    if published_dt < start_of_day_utc or published_dt > now_utc:
                        continue

                    headline = item.get("headline") or ""
                    summary = item.get("summary") or ""
                    source = item.get("source") or "Finnhub"

                    line_parts = [
                        f"Source: {source}",
                        "Section: Finnhub-general",
                    ]
                    if headline:
                        line_parts.append(f"Title: {headline}")
                    if summary:
                        line_parts.append(f"Summary: {summary}")
                    news_items.append(" | ".join(line_parts))
        except Exception as e:
            print(f"Finnhub Error: {e}")

    # Source 3: NewsAPI (Global Macro Business Headlines)
    if NEWSAPI_KEY:
        try:
            url = (
                "https://newsapi.org/v2/top-headlines?category=business"
                "&language=en"
                f"&apiKey={NEWSAPI_KEY}"
            )
            res = requests.get(url)
            data = res.json() if hasattr(res, "json") else {}
            articles = data.get("articles") or []
            for item in articles:
                published_at = item.get("publishedAt")
                if not published_at:
                    continue
                # publishedAt is an ISO8601 string in UTC, e.g. "2025-12-01T17:45:00Z"
                try:
                    published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except Exception:
                    continue

                if published_dt < start_of_day_utc or published_dt > now_utc:
                    continue

                title = item.get("title") or ""
                description = (
                    item.get("description")
                    or item.get("content")
                    or ""
                )
                source_obj = item.get("source") or {}
                source_name = source_obj.get("name") or "NewsAPI"

                line_parts = [
                    f"Source: {source_name}",
                    "Section: NewsAPI-business",
                ]
                if title:
                    line_parts.append(f"Title: {title}")
                if description:
                    line_parts.append(f"Description: {description}")
                news_items.append(" | ".join(line_parts))
        except Exception as e:
            print(f"NewsAPI Error: {e}")

    # Print total count at the end
    print(f"Total news items fetched today: {len(news_items)}")

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
    3. Format: Daily market summary that sales trader can use to brief clients in an easy-to-read and professional format.
    4. Structure:
       - Market Levels (Keep it brief)
       - The Narrative (Deep logic analysis: Why are things moving? Connection between rates/FX/Commodities)
       - Watchlist (What to look for next, in brief)
       - Quick key technical levels (trading cues)

    """
    
    if LANGUAGE_MODE == "MIXED":
        lang_instruction = """
        Output Language: 'Chinglish' (Chinese grammar with professional English Terminology).
        Example: "US 10Y Yield 突破关键节点，预示市场正在 re-price 年底前 Fed 再加息一次的概率。如果 PCE 数据超预期，VIX 可能会 spike 到 25 以上，此时避险情绪将主导跨资产相关性，建议减少 equity exposure，在此位置 long USDCNY 依然是 carry 和 hedge 的较好选择。"
        Use English for: Financial terms (Duration, Convexity, Bear Steepening, Pivot), some Action verbs (Re-price, Rally, Sell-off), Asset classes.
        Use Chinese for: All other terms and phrases, keep native Chinese logic and expressions.
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
            model="gpt-5-mini", # Use latest model for analysis
            messages=[
                {"role": "system", "content": system_prompt + lang_instruction},
                {"role": "user", "content": user_content}
            ],
            temperature=1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating analysis: {e}"

# ================= NOTIFICATION MODULE =================
def send_notification(content):
    if not SLACK_WEBHOOK_URL:
        print("No Slack Webhook URL set. Printing to console.")
        print(content)
        return

    # Adapting for Feishu/Lark (JSON format)
    # If using Slack, change payload structure accordingly
    payload_feishu = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }

    payload_slack = {
        "text": content
    }
    
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload_slack)
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