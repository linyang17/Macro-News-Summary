import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
FMP_API_KEY = os.getenv("FMP_API_KEY")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
MARKET_AUX_API_KEY = os.getenv("MARKET_AUX_API_KEY")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

LANGUAGE = "MIXED"    # EN, CN, MIXED
LANGUAGE_MODE = os.getenv("LANGUAGE_MODE", LANGUAGE)
