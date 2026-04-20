import feedparser
import requests
import os
import json
from datetime import datetime

# ---------- 你的RSS源列表（可根据需要增删）----------
RSS_FEEDS = [
    "https://www.semiinsights.com/feed",          # 半导体行业观察
    "https://www.jiweicn.com/rss",                # 集微网
    "https://www.eetimes.com/feed",               # EE Times
    "https://semiengineering.com/feed",           # Semiconductor Engineering
    "https://wallstreetcn.com/news/rss",          # 华尔街见闻热点
    "http://feeds.reuters.com/reuters/technologyNews",  # 路透科技
    "https://nvidianews.nvidia.com/news-releases/rss.xml", # 英伟达
    "https://pr.tsmc.com/rss",                    # 台积电
    "https://news.samsung.com/global/rss",        # 三星
]

def fetch_articles():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:  # 每个源最多取5条最新
                articles.append({
                    "title": entry.get("title", "无标题"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:200],  # 截取前200字符
                    "source": feed.feed.get("title", url)
                })
        except Exception as e:
            print(f"抓取失败 {url}: {e}")
    return articles

def ask_deepseek(articles, api_key):
    # 组装提示词
    prompt = f"""你是半导体行业分析师。今天是{datetime.now().strftime('%Y-%m-%d')}。
请根据以下新闻标题和摘要，生成一份简洁的早报，每条新闻用一句话概括发生了什么，并附上原文链接。
按重要性排序。最后加一段总结。

新闻列表：
"""
    for idx, art in enumerate(articles[:30], 1):  # 最多处理30条
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n请输出Markdown格式，标题为【半导体早报】，不要多余的解释。"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
    return resp.json()["choices"][0]["message"]["content"]

def send_wechat(content, token):
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": f"半导体早报 {datetime.now().strftime('%Y-%m-%d')}",
        "content": content,
        "template": "markdown"
    }
    requests.post(url, json=data)

if __name__ == "__main__":
    print("开始抓取新闻...")
    arts = fetch_articles()
    print(f"抓取到 {len(arts)} 条原始新闻")
    if not arts:
        print("无新闻，退出")
        exit(0)
    
    api_key = os.environ["DEEPSEEK_API_KEY"]
    print("调用DeepSeek生成摘要...")
    report = ask_deepseek(arts, api_key)
    
    # 发送到微信（如果你选择PushPlus）
    token = os.environ.get("PUSHPLUS_TOKEN")
    if token:
        send_wechat(report, token)
        print("已发送到微信")
    else:
        print("未设置PUSHPLUS_TOKEN，仅打印报告：")
        print(report)
