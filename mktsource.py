from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree
import requests
import yfinance as yf

from config import (
    NEWS_API_KEY,
    FINNHUB_API_KEY,
    ALPHAVANTAGE_API_KEY,
    FMP_API_KEY,
    MARKET_AUX_API_KEY,
)
from tickers import MARKET_TICKERS


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _within_window(published_dt: datetime, start_time: datetime, end_time: datetime) -> bool:
    published_dt = _ensure_utc(published_dt)
    return start_time <= published_dt <= end_time


def _format_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_rss_feed(url: str, source_name: str, section: str, start_time: datetime, end_time: datetime, news_items: list[str]):
    try:
        res = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MacroNewsBot/1.0; +https://example.com)"
            },
        )
        res.raise_for_status()
        root = ElementTree.fromstring(res.content)
        for item in root.findall(".//item"):
            pub_date_text = item.findtext("pubDate")
            if not pub_date_text:
                continue
            try:
                published_dt = parsedate_to_datetime(pub_date_text)
            except Exception:
                continue

            if not _within_window(published_dt, start_time, end_time):
                continue

            title = item.findtext("title") or ""
            description = item.findtext("description") or ""

            line_parts = [
                f"Source: {source_name}",
                f"Section: {section}",
            ]
            if title:
                line_parts.append(f"Title: {title}")
            if description:
                line_parts.append(f"Summary: {description}")
            news_items.append(" | ".join(line_parts))
    except Exception as exc:
        print(f"{source_name} RSS Error: {exc}")


def fetch_news(start_time: datetime, end_time: datetime) -> str:
    """
    Fetch macro/rates/FX news published between start_time and end_time (UTC).
    All sources are filtered strictly within the requested window so Cloud
    Scheduler time changes automatically update the news range.
    """

    start_time = _ensure_utc(start_time)
    end_time = _ensure_utc(end_time)
    if start_time > end_time:
        raise ValueError("start_time must be earlier than end_time")

    news_items: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    # Source 1: Yahoo Finance
    try:
        all_symbols = [sym for symbols in MARKET_TICKERS.values() for sym in symbols]
        yahoo_count = 0

        yahoo_window_start = _ensure_utc(start_time)
        yahoo_window_end = _ensure_utc(end_time)

        for ticker in all_symbols:
            try:
                yf_ticker = yf.Ticker(ticker)
            except Exception as e:
                print(f"Yahoo News Warning: failed to init Ticker {ticker}: {e}")
                continue

            try:
                # yfinance.Ticker.get_news supports count and tab="news"/"all"/"press releases"
                news_list = yf_ticker.get_news(count=50, tab="all")
            except Exception:
                news_list = getattr(yf_ticker, "news", None) or []

            print(f"Yahoo News Debug: ticker={ticker}, raw_news_count={len(news_list)}")
            for item in news_list:
                ts = item.get("providerPublishTime")
                if not ts:
                    continue
                published_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                if not _within_window(published_dt, yahoo_window_start, yahoo_window_end):
                    continue

                title = item.get("title") or ""
                summary = item.get("summary") or ""
                source = "Yahoo Finance"

                key = (source, title)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                line_parts = [
                    f"Source: {source}",
                    f"Section: Yahoo-{ticker}",
                ]
                if title:
                    line_parts.append(f"Title: {title}")
                if summary:
                    line_parts.append(f"Summary: {summary}")
                
                yahoo_count += 1
                news_items.append(" | ".join(line_parts))
        print(f"Yahoo News Debug: symbols={len(all_symbols)}, items_added={yahoo_count}")
    except Exception as e:
        print(f"Yahoo News Error: {e}")

    # Source 2: Finnhub (General + Forex categories)
    if FINNHUB_API_KEY:
        for category in ("general", "forex"):
            try:
                url = f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_API_KEY}"
                res = requests.get(url, timeout=10)
                data = res.json() if hasattr(res, "json") else []
                if isinstance(data, list):
                    for item in data:
                        ts = item.get("datetime")
                        if not ts:
                            continue
                        published_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        if not _within_window(published_dt, start_time, end_time):
                            continue

                        headline = item.get("headline") or ""
                        summary = item.get("summary") or ""
                        source = item.get("source") or "Finnhub"

                        key = (source, headline)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        line_parts = [
                            f"Source: {source}",
                            f"Section: Finnhub-{category}",
                        ]
                        if headline:
                            line_parts.append(f"Title: {headline}")
                        if summary:
                            line_parts.append(f"Summary: {summary}")
                        news_items.append(" | ".join(line_parts))
            except Exception as e:
                print(f"Finnhub {category} Error: {e}")

    # Source 3: NewsAPI (Macro & FX keywords)
    if NEWS_API_KEY:
        try:
            query = (
                "macroeconomics OR macroeconomic OR \"central bank\" OR \"interest rate\" "
                "OR forex OR FX OR currency OR \"foreign exchange\""
            )
            params = {
                "q": query,
                "language": "en",
                "pageSize": 100,
                "sortBy": "publishedAt",
                "from": _format_time(start_time),
                "to": _format_time(end_time),
                "apiKey": NEWS_API_KEY,
            }
            res = requests.get("https://newsapi.org/v2/everything", params=params, timeout=10)
            data = res.json() if hasattr(res, "json") else {}
            articles = data.get("articles") or []
            for item in articles:
                published_at = item.get("publishedAt")
                if not published_at:
                    continue
                try:
                    published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except Exception:
                    continue

                if not _within_window(published_dt, start_time, end_time):
                    continue

                title = item.get("title") or ""
                description = item.get("description") or item.get("content") or ""
                source_obj = item.get("source") or {}
                source_name = source_obj.get("name") or "NewsAPI"

                key = (source_name, title)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                line_parts = [
                    f"Source: {source_name}",
                    "Section: NewsAPI-macro-fx",
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
            av_topics = [
                "forex",
                "financial_markets",
                "economy_fiscal",
                "economy_monetary",
                "economy_macro",
                "energy_transportation",
            ]
            for topic in av_topics:
                params = {
                    "function": "NEWS_SENTIMENT",
                    "topics": topic,  # 单个 topic
                    "time_from": start_time.strftime("%Y%m%dT%H%M"),
                    "time_to": end_time.strftime("%Y%m%dT%H%M"),
                    "apikey": ALPHAVANTAGE_API_KEY,
                }
                res = requests.get("https://www.alphavantage.co/query", params=params, timeout=10)
                data = res.json() if hasattr(res, "json") else {}
                feed = data.get("feed") or []

                for item in feed:
                    tp = item.get("time_published")
                    if not tp:
                        continue
                    try:
                        published_dt = datetime.strptime(tp, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                    except Exception:
                        continue

                    if not _within_window(published_dt, start_time, end_time):
                        continue

                    title = item.get("title") or ""
                    summary = item.get("summary") or ""
                    source = item.get("source") or "AlphaVantage"

                    key = (source, title)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    line_parts = [
                        f"Source: {source}",
                        f"Section: AlphaVantage-{topic}",
                    ]
                    if title:
                        line_parts.append(f"Title: {title}")
                    if summary:
                        line_parts.append(f"Summary: {summary}")
                    news_items.append(" | ".join(line_parts))
        except Exception as e:
            print(f"AlphaVantage Error: {e}")
    # Source 5: Financial Modeling Prep – Forex News
    if FMP_API_KEY:
        try:
            params = {
                "page": 0,
                "limit": 100,
                "apikey": FMP_API_KEY,
            }
            res = requests.get(
                "https://financialmodelingprep.com/stable/fmp-articles",
                params=params,
                timeout=10,
            )
            data = []
            try:
                res.raise_for_status()
                data = res.json()
            except Exception as exc:
                # If this endpoint is not available under the current subscription,
                # just log once and skip without treating it as a hard error.
                status = getattr(res, "status_code", None)
                if status == 402:
                    print("FMP Info: fmp-articles endpoint not available under current subscription (402), skipping FMP Forex source.")
                else:
                    print(f"FMP Error: {exc} (status={status})")
            if isinstance(data, list):
                for item in data:
                    published_at = item.get("publishedDate") or item.get("published_at")
                    if not published_at:
                        continue
                    try:
                        published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    except Exception:
                        continue

                    if not _within_window(published_dt, start_time, end_time):
                        continue

                    title = item.get("title") or ""
                    text = item.get("text") or ""
                    source = item.get("site") or item.get("publisher") or "FinancialModelingPrep"

                    key = (source, title)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

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
            print(f"FMP Error: {e}")


    # Source 6: MarketAux – Financial / FX News
    if MARKET_AUX_API_KEY:
        try:
            params = {
                "api_token": MARKET_AUX_API_KEY,
                "entity_types": "index,currency",
                "language": "en",
                "sort": "published_at:desc",
                "limit": 100,
                "published_after": _format_time(start_time),
                "published_before": _format_time(end_time),
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

                if not _within_window(published_dt, start_time, end_time):
                    continue

                title = item.get("title") or ""
                description = item.get("description") or item.get("snippet") or ""
                source = item.get("source") or "MarketAux"

                key = (source, title)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

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

    # Source 7: Bloomberg Newsletters (RSS)
    bloomberg_feeds = {
        "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
        "Bloomberg Economics": "https://feeds.bloomberg.com/economics/news.rss",
        "Bloomberg Opinions": "https://feeds.bloomberg.com/bview/news.rss",
    }
    for name, url in bloomberg_feeds.items():
        _parse_rss_feed(url, name, "Bloomberg-newsletter", start_time, end_time, news_items)

    # Source 8: FXStreet (RSS)
    fxstreet_feeds = {
        "FXStreet News": "https://www.fxstreet.com/rss/news",
        "FXStreet Analysis": "https://www.fxstreet.com/rss/analysis",
    }
    for name, url in fxstreet_feeds.items():
        _parse_rss_feed(url, name, "FXStreet", start_time, end_time, news_items)


    # Source 9: Central Bank official releases (rates / govies)
    central_bank_feeds = {
        # Federal Reserve monetary policy press releases
        "Fed Monetary Policy": "https://www.federalreserve.gov/feeds/press_monetary.xml",
        # ECB combined press / speeches / press conferences feed
        "ECB Press": "https://www.ecb.europa.eu/rss/press.html",
        # Bank of England news (includes MPC, rate decisions, speeches)
        "BoE News": "https://www.bankofengland.co.uk/rss/news",
        # Reserve Bank of Australia media releases (includes monetary policy decisions)
        "RBA Media Releases": "https://www.rba.gov.au/rss/rss-cb-media-releases.xml",
    }
    for name, url in central_bank_feeds.items():
        _parse_rss_feed(
            url,
            name,
            f"CB-{name}",
            start_time,
            end_time,
            news_items,
        )

    # Print total count at the end
    print(f"Total news items fetched between {start_time} and {end_time}: {len(news_items)}")

    return "\n".join(news_items)
