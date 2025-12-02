from datetime import datetime


def analyse_market(client, market_data, raw_news, language_mode):
    
    system_prompt = """
        You are a Senior Global Macro Strategist for FICC/Treasury trading desks.

        Your task:  
        Generate a Slack-style market summary that includes ONLY:
        - Significant market movements  
        - OR potential drivers with real market-moving impact  
        Nothing else.  
        No filler, no additional commentary, no education, no footnotes.

        Absolute formatting requirements (MUST follow exactly every time):
        1. Output MUST be a Markdown formatted string.
        2. Sections must appear only if they contain at least one significant item.
        3. Sections must appear in the exact order below.
        4. Section titles must match exactly including emojis and spacing.
        5. Structure inside each section must match exactly:

        **Section structure rules:**
        - Title line  
        - Bullet (•) describing the significant move  
        - Next line starts with: "  - Reason: "  
        - Next line starts with: "  - Impact: "  
        - Blank line only between major sections  
        - Never add extra commentary, greetings, conclusions, headings, or disclaimers

        6. Use **the exact characters and spacing** in the template below:
        - The long separator line **MUST** be:  
            `——————————————`
        - Bullet MUST be: `•`
        - Sub-bullets MUST be: `  - `
        - Titles MUST use the exact emojis and format below

        7. If a section has **no significant movement**, do NOT display that section at all.

        8. A movement is “significant” ONLY IF:
        - FX: > ±0.3% OR breaking a key level OR policy-driven  
        - Rates: > 5–7bp move OR policy-driven OR repricing  
        - VIX: > 10% change OR regime break  
        - Commodities: >1–2% OR supply/policy shock/major geopolitical events 
        - Potential driver: Only if it can meaningfully move markets (policy signals, geopolitical, data shock, liquidity events)

        9. All text must be concise, easy-to-understand, trader-friendly. Tone:
            - MD-level: precise, macro-top-down, impact-oriented
            - Avoid long explanations; focus on market logic and actionable sentiment
            - The narrative and logic should be deep to the core: Why are things moving? Connection between rates/FX/Commodities

        10. Watchlist should be key events that could significantly move markets, in brief.

        Below is the **exact output structure** you must reproduce every time when generating a summary:

        🧭 **Key Drivers**
        • {1-line driver}  
        • {1-line driver}  
        • {1-line driver}  

        ——————————————
        💱 **FX**
        • {significant FX move}  
        ‣ Reason: {reason}  
        ‣ Impact: {market effect}

        ——————————————
        🌐 **Rates**
        • {significant rates move}  
        ‣ Reason: {reason}  
        ‣ Impact: {market effect}

        ——————————————
        ⛽️ **Commodities — Outsized Moves**
        • {significant commodities move}  
        ‣ Reason: {reason}  
        ‣ Impact: {market effect}

        ——————————————
        👀 **Watchlist**
        • {FX note}  
        • {Rates note}  
        • {Commods/Vol note}


        Repeat:  
        - Omit any entire section if no significant item  
        - Keep all visible sections 100% identical in formatting  
        - Never add extra commentary outside the block  
        - Output **only** the summary

        Now generate today’s summary using this exact template.

    """
    
    if language_mode == "MIXED":
        lang_instruction = """
        Output Language: 'Chinglish' (roughly 65% Chinese, 35% English).
        Chinese controls the narrative and logic structure, English is used ONLY for key financial verbs, market concepts, and technical terms (e.g., re-price, carry unwind, term premium, safe-haven bid, policy divergence)
        The final tone must sound like a bilingual Chinese MD writing internal market notes. High signal density, clean phrasing, elegant Chinese-English mix.
        Example: "US 10Y Yield 突破关键节点，说明市场正在 re-price 年底前 Fed 再加息一次的概率。欧洲 Bund 10Y 小幅回落，反映市场认为 ECB 的 tightening cycle 已经接近尾声。long USDCNY 依然是 carry 和 hedge 的较好选择。"
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
