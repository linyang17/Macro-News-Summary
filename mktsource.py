from datetime import datetime, timezone
import requests
import yfinance as yf
from config import NEWS_API_KEY, FINNHUB_API_KEY
from markets import MARKET_TICKERS



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
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
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
    if NEWS_API_KEY:
        try:
            url = (
                "https://newsapi.org/v2/top-headlines?category=business"
                "&language=en"
                f"&apiKey={NEWS_API_KEY}"
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
