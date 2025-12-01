import os
from dotenv import load_dotenv
load_dotenv()  # 在本地调试时有效，云端无所谓

from main import job

def run_news(request):
    """
    Cloud Functions （HTTP trigger）
    """
    # 可选：从 request 里读一些参数，比如语言模式等
    job()
    return ("ok", 200)
