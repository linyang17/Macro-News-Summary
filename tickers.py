import yfinance as yf
from datetime import datetime


# ================= MARKET OF INTEREST =================
# Shared tickers universe for both market snapshot and news fetching
MARKET_TICKERS = {
    "FX": ["EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "CNY=X"], 
    "RATES": ["^TNX", "^FVX", "^IRX"],  # 10Y, 5Y, 13-Week (Proxy for short term)
    "COMMO": ["GC=F", "CL=F"],  # Gold, Crude Oil
    "INDEX": ["^GSPC", "^IXIC", "^HSI"],  # SPX, Nasdaq, Hang Seng
    "VIX": ["^VIX"],
}


# ================= MARKET DATA MODULE =================
def get_market_snapshot():
    
    tickers = MARKET_TICKERS

    data_str = "**Market Snapshot** \n"
    
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
                
                data_str += f" {name}: {price:.4f} ({change_pct:+.2f}%)\n"
            except:
                continue
        data_str += "------------------\n"
    
    return data_str

