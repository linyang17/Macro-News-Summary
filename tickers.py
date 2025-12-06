import yfinance as yf
from datetime import datetime


# ================= MARKET OF INTEREST =================
# Shared tickers universe for both market snapshot and news fetching
MARKET_TICKERS = {
  "FX": [
    "EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X",
    "USDCAD=X", "USDCHF=X", "USDNOK=X", "USDSEK=X",
    "USDCNH=X", "CNY=X", "CNH=X",
    "EURJPY=X", "EURGBP=X"
  ],

  "RATES": {
    "UST_Yields": [
      "^IRX",   #13-week T-bill
      "^FVX",   # 5-year Treasury yield
      "^TNX",   # 10-year Treasury yield
      "^TYX"    # 30-year Treasury yield
    ],
    "UST_Futures": [
      "ZB=F",   # 30Y Bond Future
      "ZN=F",   # 10Y Note Future
      "ZF=F",   # 5Y Note Future
      "ZT=F"    # 2Y Note Future
    ],
    "STIRs": [
      "SR3=F",  # SOFR futures (generic)
      "GE=F"    # Eurodollar legacy (still used historically)
    ],
    "Swaps_Proxies": [
      "^UST2Y", "^UST5Y", "^UST10Y", "^UST30Y"
    ]
  },

  "COMMO": {
    "Metals": [
      "GC=F",   # Gold
      "SI=F",   # Silver
      "HG=F"    # Copper
    ],
    "Energy": [
      "CL=F",   # WTI Crude Oil
      "BZ=F",   # Brent
      "NG=F"    # Natural Gas
    ],
    "Agriculture": [
      "ZS=F",   # Soybean
      "ZC=F",   # Corn
      "ZW=F"    # Wheat
    ]
  }
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

