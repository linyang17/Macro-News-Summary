from datetime import datetime, timezone
import requests
import yfinance as yf
from config import NEWS_API_KEY, FINNHUB_API_KEY, ALPHAVANTAGE_API_KEY, FMP_API_KEY, NEWSDATA_API_KEY, MARKET_AUX_API_KEY
from tickers import MARKET_TICKERS



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



    # Source 4: Alpha Vantage News & Sentiment (Macro & FX)
    if ALPHAVANTAGE_API_KEY:
        try:
            time_from = start_of_day_utc.strftime("%Y%m%dT%H%M")
            time_to = now_utc.strftime("%Y%m%dT%H%M")

            params = {
                "function": "NEWS_SENTIMENT",
                # Focus on macro / FX related topics
                "topics": "forex,financial_markets,economic",
                "time_from": time_from,
                "time_to": time_to,
                "apikey": ALPHAVANTAGE_API_KEY,
            }
            res = requests.get("https://www.alphavantage.co/query", params=params, timeout=10)
            data = res.json() if hasattr(res, "json") else {}
            feed = data.get("feed") or []
            for item in feed:
                # Alpha Vantage uses `time_published`: e.g. "20251201T174500"
                tp = item.get("time_published")
                if not tp:
                    continue
                try:
                    published_dt = datetime.strptime(tp, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                if published_dt < start_of_day_utc or published_dt > now_utc:
                    continue

                title = item.get("title") or ""
                summary = item.get("summary") or ""
                source = item.get("source") or "AlphaVantage"

                line_parts = [
                    f"Source: {source}",
                    "Section: AlphaVantage-macro-fx",
                ]
                if title:
                    line_parts.append(f"Title: {title}")
                if summary:
                    line_parts.append(f"Summary: {summary}")
                news_items.append(" | ".join(line_parts))
        except Exception as e:
            print(f"AlphaVantage Error: {e}")

    # Source 5: Financial Modeling Prep – Forex News
    # Docs: https://site.financialmodelingprep.com/developer/docs/stable/search-forex-news
    if FMP_API_KEY:
        try:
            params = {
                # leave it empty to get broad FX coverage.
                # "symbols": "EURUSD,USDJPY,GBPUSD",
                "page": 0,
                "limit": 50,
                "apikey": FMP_API_KEY,
            }
            res = requests.get(
                "https://financialmodelingprep.com/stable/news/forex-latest",
                params=params,
                timeout=10,
            )
            data = res.json() if hasattr(res, "json") else []
            if isinstance(data, list):
                for item in data:
                    published_at = item.get("publishedDate") or item.get("published_at")
                    if not published_at:
                        continue
                    try:
                        published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    except Exception:
                        continue

                    if published_dt < start_of_day_utc or published_dt > now_utc:
                        continue

                    title = item.get("title") or ""
                    text = item.get("text") or ""
                    source = item.get("site") or item.get("publisher") or "FMP-Forex"

                    line_parts = [
                        f"Source: {source}",
                        "Section: FMP-forex",
                    ]
                    if title:
                        line_parts.append(f"Title: {title}")
                    if text:
                        line_parts.append(f"Summary: {text}")
                    news_items.append(" | ".join(line_parts))
        except Exception as e:
            print(f"FMP Forex Error: {e}")

    # Source 6: NewsData.io – Global Macro / FX Headlines
    # Docs: https://newsdata.io
    if NEWSDATA_API_KEY:
        try:
            # Use keyword query to tilt towards macro/FX
            # You can further tune the `q` string based on效果.
            params = {
                "apikey": NEWSDATA_API_KEY,
                "q": "(forex OR FX OR currency OR \"central bank\" OR \"interest rate\" OR macro)",
                "language": "en",
                # business / economy style categories, but may vary by plan
                # "category": "business,economy",
                "page": 0,
            }
            res = requests.get("https://newsdata.io/api/1/latest", params=params, timeout=10)
            data = res.json() if hasattr(res, "json") else {}
            articles = data.get("results") or data.get("articles") or []
            for item in articles:
                published_at = item.get("pubDate") or item.get("publishedAt")
                if not published_at:
                    continue
                # NewsData 有时是 ISO8601 字符串
                try:
                    published_dt = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00").split(" ")[0].replace("+00:00", "")
                    )
                    # 如果没有时区信息，强制设为 UTC
                    if published_dt.tzinfo is None:
                        published_dt = published_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                if published_dt < start_of_day_utc or published_dt > now_utc:
                    continue

                title = item.get("title") or ""
                description = item.get("description") or item.get("content") or ""
                source = item.get("source_id") or item.get("source") or "NewsData"

                line_parts = [
                    f"Source: {source}",
                    "Section: NewsData-macro-fx",
                ]
                if title:
                    line_parts.append(f"Title: {title}")
                if description:
                    line_parts.append(f"Summary: {description}")
                news_items.append(" | ".join(line_parts))
        except Exception as e:
            print(f"NewsData Error: {e}")

    # Source 7: MarketAux – Financial / FX News
    # Docs: https://www.marketaux.com/
    if MARKET_AUX_API_KEY:
        try:
            params = {
                "api_token": MARKET_AUX_API_KEY,
                # focus on forex + macro
                "filter_entities": "forex,macro",  # may vary by plan; adjust per docs
                "language": "en",
                "sort": "published_at:desc",
                "limit": 50,
            }
            res = requests.get("https://api.marketaux.com/v1/news/all", params=params, timeout=10)
            data = res.json() if hasattr(res, "json") else {}
            articles = data.get("data") or []
            for item in articles:
                published_at = item.get("published_at")
                if not published_at:
                    continue
                try:
                    published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except Exception:
                    continue

                if published_dt < start_of_day_utc or published_dt > now_utc:
                    continue

                title = item.get("title") or ""
                description = item.get("description") or item.get("snippet") or ""
                source = item.get("source") or "MarketAux"

                line_parts = [
                    f"Source: {source}",
                    "Section: MarketAux-macro-fx",
                ]
                if title:
                    line_parts.append(f"Title: {title}")
                if description:
                    line_parts.append(f"Summary: {description}")
                news_items.append(" | ".join(line_parts))
        except Exception as e:
            print(f"MarketAux Error: {e}")

    # Print total count at the end
    print(f"Total news items fetched today: {len(news_items)}")

    return "\n".join(news_items)
