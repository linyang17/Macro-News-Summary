import time
import schedule
from datetime import datetime, time as dt_time, timedelta, timezone
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ================= MODULES =================
from config import (
    OPENAI_API_KEY,
    LANGUAGE_MODE,
    SCHEDULE_UTC_TIMES,
    DEFAULT_LOOKBACK_HOURS,
)
from tickers import get_market_snapshot
from mktsource import fetch_news
from analysis import analyse_market
from notification import send_msg_slack


LAST_RUN_UTC: datetime | None = None


def _parse_schedule_times(value: str) -> list[dt_time]:
    times: list[dt_time] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            hour, minute = map(int, chunk.split(":"))
            times.append(dt_time(hour=hour, minute=minute, tzinfo=timezone.utc))
        except ValueError:
            print(f"Invalid schedule time skipped: {chunk}")
    return sorted(times)


def _previous_schedule_datetime(now_utc: datetime) -> datetime:
    schedule_times = _parse_schedule_times(SCHEDULE_UTC_TIMES)
    if not schedule_times:
        return now_utc - timedelta(hours=DEFAULT_LOOKBACK_HOURS)

    today_candidates = [
        datetime(
            year=now_utc.year,
            month=now_utc.month,
            day=now_utc.day,
            hour=t.hour,
            minute=t.minute,
            tzinfo=timezone.utc,
        )
        for t in schedule_times
    ]
    previous_runs = [ts for ts in today_candidates if ts <= now_utc]
    if previous_runs:
        return max(previous_runs)

    # If no earlier run today, pick the last time from previous day
    last_time = schedule_times[-1]
    yesterday = now_utc - timedelta(days=1)
    return datetime(
        year=yesterday.year,
        month=yesterday.month,
        day=yesterday.day,
        hour=last_time.hour,
        minute=last_time.minute,
        tzinfo=timezone.utc,
    )


def _compute_time_window(now_utc: datetime) -> tuple[datetime, datetime]:
    global LAST_RUN_UTC
    if LAST_RUN_UTC:
        start_time = LAST_RUN_UTC
    else:
        start_time = _previous_schedule_datetime(now_utc)
    LAST_RUN_UTC = now_utc
    return start_time, now_utc


# ================= MAIN LOGIC =================
def job():
    now_utc = datetime.now(timezone.utc)
    start_time, end_time = _compute_time_window(now_utc)
    print(f"Starting job at {now_utc} covering {start_time} to {end_time}...")

    # 1. Get Data
    mkt_data = get_market_snapshot()
    news_data = fetch_news(start_time, end_time)

    # 2. Analyze
    client = OpenAI(api_key=OPENAI_API_KEY)
    report = analyse_market(client, mkt_data, news_data, LANGUAGE_MODE)

    # 3. Send
    final_output = f"📅 Global Macro Brief | {now_utc.strftime('%Y-%m-%d %H:%M')} \n {report}"
    send_msg_slack(final_output)


if __name__ == "__main__":
    for t in _parse_schedule_times(SCHEDULE_UTC_TIMES):
        schedule.every().day.at(t.strftime("%H:%M")).do(job)

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
