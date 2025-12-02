from datetime import datetime


def analyse_market(client, market_data, raw_news, language_mode):
    
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
    
    if language_mode == "MIXED":
        lang_instruction = """
        Output Language: 'Chinglish' (Chinese grammar with professional English Terminology).
        Example: "US 10Y Yield 突破关键节点，预示市场正在 re-price 年底前 Fed 再加息一次的概率。如果 PCE 数据超预期，VIX 可能会 spike 到 25 以上，此时避险情绪将主导跨资产相关性，建议减少 equity exposure，在此位置 long USDCNY 依然是 carry 和 hedge 的较好选择。"
        Use English for: Financial terms (Duration, Convexity, Bear Steepening, Pivot), some Action verbs (Re-price, Rally, Sell-off), Asset classes.
        Use Chinese for: All other terms and phrases, keep native mandarin Chinese logic and expressions.
        """
    elif language_mode == "EN":
        lang_instruction = "Output Language: Professional English."
    elif language_mode == "CN":
        lang_instruction = "Output Language: Professional mandarin Chinese."
    else:
        raise ValueError(f"Language not supported: {language_mode}")


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
