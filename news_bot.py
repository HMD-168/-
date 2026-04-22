print("SCRIPT STARTED", flush=True)
import feedparser
import requests
import os
import json
from datetime import datetime

# ---------- RSS源列表 ----------
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

def fetch_articles(limit_per_source=10):
    """每个源最多抓取 limit_per_source 条，返回文章列表"""
    articles = []
    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:limit_per_source]:
                articles.append({
                    "title": entry.get("title", "无标题"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:200],
                    "source": feed.feed.get("title", url),
                    "published": entry.get("published", "")
                })
        except Exception as e:
            print(f"抓取失败 {url}: {e}")
    return articles

def calculate_hot_score(article):
    """热度评分：来源权重 + 关键词匹配"""
    title = article['title'].lower()
    source = article['source'].lower()
    score = 0
    # 高权重来源
    high_sources = ["reuters", "eetimes", "semiengineering", "华尔街见闻", "路透", "semiconductor"]
    for hs in high_sources:
        if hs in source:
            score += 10
            break
    # 热门关键词
    keywords = ["ai", "芯片", "制裁", "突破", "收购", "财报", "台积电", "中芯国际", "存储", 
                "nvidia", "intel", "amd", "asml", "华为", "量子", "产能", "涨价", "禁令", "补贴"]
    for kw in keywords:
        if kw in title:
            score += 2
    return score

def ask_deepseek(articles, api_key):
    """调用 DeepSeek API 生成早报"""
    # 构建提示词，要求突出前10条为热门
    prompt = f"""你是半导体行业分析师。今天是{datetime.now().strftime('%Y-%m-%d')}。
请根据以下新闻标题和摘要，生成一份简洁的早报。
要求：
- 总共 {len(articles)} 条新闻，其中前10条是🔥热门新闻，请在标题前标注【热门】。
- 每条新闻用一句话概括发生了什么，并附上原文链接。
- 按重要性排序（热门新闻在前）。
- 最后加一段总结。

新闻列表：
"""
    for idx, art in enumerate(articles, 1):
        tag = "🔥热门 " if idx <= 10 else ""
        prompt += f"{idx}. {tag}{art['title']} | {art['summary']} | 链接：{art['link']}\n"
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
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            raise Exception(f"API错误: {data['error']}")
        else:
            raise Exception(f"未知响应格式: {data}")
    except requests.exceptions.Timeout:
        raise Exception("DeepSeek API 请求超时（60秒）")
    except requests.exceptions.RequestException as e:
        raise Exception(f"DeepSeek API 请求失败: {e}")

def send_wechat(content, token):
    """通过 Server酱 推送消息"""
    url = f"https://sctapi.ftqq.com/{token}.send"
    data = {
        "title": f"半导体早报 {datetime.now().strftime('%Y-%m-%d')}",
        "desp": content,
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        print(f"Server酱 推送响应: {resp.json()}")
    except Exception as e:
        print(f"Server酱 推送失败: {e}")

if __name__ == "__main__":
    print("MAIN ENTERED", flush=True)
    print("开始抓取新闻...")
    arts = fetch_articles(limit_per_source=10)   # 每个源最多10条
    print(f"抓取到 {len(arts)} 条原始新闻")
    if not arts:
        print("无新闻，退出")
        exit(0)
    
    # 计算热度分，排序并取前10为热门，再取后续40条（总50条）
    for art in arts:
        art['hot_score'] = calculate_hot_score(art)
    sorted_arts = sorted(arts, key=lambda x: x['hot_score'], reverse=True)
    hot_news = sorted_arts[:10]
    other_news = sorted_arts[10:50]   # 最多再取40条
    final_news = hot_news + other_news
    print(f"筛选后共 {len(final_news)} 条（其中热门 {len(hot_news)} 条）")
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：未设置 DEEPSEEK_API_KEY 环境变量")
        exit(1)
    
    print("调用DeepSeek生成摘要...")
    try:
        report = ask_deepseek(final_news, api_key)
        print("DeepSeek 返回成功")
    except Exception as e:
        print(f"DeepSeek API 调用失败: {e}")
        exit(1)
    
    # 在日志中打印报告（方便直接查看）
    print("=== 生成的早报内容 ===")
    print(report)
    print("=== 早报结束 ===")
    
    token = os.environ.get("PUSHPLUS_TOKEN")   # 注意：Secret 名字还是 PUSHPLUS_TOKEN，里面存的是 Server酱 的 SendKey
    if token:
        send_wechat(report, token)
        print("已发送到微信")
    else:
        print("未设置 PUSHPLUS_TOKEN，仅打印报告")
