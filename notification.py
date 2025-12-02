import requests
from config import SLACK_WEBHOOK_URL


def send_msg_slack(content, slack_url=SLACK_WEBHOOK_URL):
    if not slack_url:
        print("No Slack Webhook URL set. Printing to console.")
        print(content)
        return

    payload_slack = {
        "text": content
    }
    
    try:
        requests.post(slack_url, json=payload_slack)
        print("Slack notification sent.")
    except Exception as e:
        print(f"Slack notification Failed: {e}")

def send_msg_feishu(content, feishu_url):
    if not feishu_url:
        print("No Feishu Webhook URL set. Printing to console.")
        print(content)
        return

    payload_feishu = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }

    try:
        requests.post(feishu_url, json=payload_feishu)
        print("Feishu notification sent.")
    except Exception as e:
        print(f"Feishu notification Failed: {e}")

