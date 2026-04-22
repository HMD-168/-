print("SCRIPT STARTED", flush=True)
import feedparser
import requests
import os
import json
from datetime import datetime

# ---------- 半导体行业 RSS 源（不限总数，每个源取最新 10 条）----------
SEMI_RSS_FEEDS = [
    "https://www.semiinsights.com/feed",          # 半导体行业观察
    "https://www.jiweicn.com/rss",                # 集微网
    "https://www.eetimes.com/feed",               # EE Times
    "https://semiengineering.com/feed",           # Semiconductor Engineering
    "https://wallstreetcn.com/news/rss",          # 华尔街见闻热点（含科技）
    "http://feeds.reuters.com/reuters/technologyNews",  # 路透科技
    "https://nvidianews.nvidia.com/news-releases/rss.xml", # 英伟达
    "https://pr.tsmc.com/rss",                    # 台积电
    "https://news.samsung.com/global/rss",        # 三星
    "https://www.ithome.com/rss/",                # IT之家
    "https://www.leiphone.com/feed",              # 雷锋网
    "https://www.eet-china.com/feed",             # EET 电子工程专辑
    "https://www.2ic.cn/feed",                    # 半导体技术天地
    "https://www.moore.ren/feed",                 # 摩尔精英
]

# ---------- 社会热点 RSS 源（至少 10 条）----------
HOT_RSS_FEEDS = [
    "http://feeds.reuters.com/reuters/worldNews",          # 路透国际
    "http://feeds.bbci.co.uk/news/world/rss.xml",          # BBC 世界
    "http://rss.caixin.com/rollnews.xml",                  # 财新网
    "https://www.xinhuanet.com/fortune/news_newsroom_index_rss.xml", # 新华社
    "http://www.people.com.cn/rss/people.xml",             # 人民网
    "https://www.guancha.cn/index.rss",                    # 观察者网
    "https://www.thepaper.cn/rss_news.xml",                # 澎湃新闻
]

def fetch_articles_from_sources(rss_list, limit_per_source=10, min_total=None):
    """
    从 RSS 源列表抓取，每个源最多取 limit_per_source 条。
    如果指定 min_total，则尽量确保总数 >= min_total（通过增加每个源条数）
    """
    articles = []
    # 如果要求最少条数，动态调整每个源的上限
    if min_total:
        # 粗略估算：需要抓取的源数量 * limit 至少达到 min_total
        # 但简单起见，直接增加 limit_per_source 到 20 或更多
        dynamic_limit = max(limit_per_source, min_total // len(rss_list) + 5)
    else:
        dynamic_limit = limit_per_source
    
    for url in rss_list:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:dynamic_limit]:
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

def ask_deepseek(semi_articles, hot_articles, api_key):
    """调用 DeepSeek 生成早报"""
    prompt = f"""你是信息分析师。今天是{datetime.now().strftime('%Y-%m-%d')}。
请根据以下新闻，生成一份【半导体行业早报 + 社会热点速览】。

要求：
1. 先输出【半导体行业】板块（共{len(semi_articles)}条），每条用一句话概括发生了什么，并附上原文链接。
   - 按重要性排序（优先半导体制造、芯片、存储、通信设备等核心领域）。
2. 然后输出【社会热点】板块（共{len(hot_articles)}条），每条用一句话概括 + 原文链接，按重要性排序。
3. 最后加一段总结。
4. 使用 Markdown 格式，标题为【每日资讯简报】。

--- 半导体行业新闻 ---
"""
    for idx, art in enumerate(semi_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n--- 社会热点新闻 ---\n"
    for idx, art in enumerate(hot_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n请直接输出，不要多余的解释。"

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
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            raise Exception(f"API错误: {data['error']}")
        else:
            raise Exception(f"未知响应格式: {data}")
    except requests.exceptions.Timeout:
        raise Exception("DeepSeek API 请求超时（90秒）")
    except requests.exceptions.RequestException as e:
        raise Exception(f"DeepSeek API 请求失败: {e}")

def send_wechat(content, token):
    """通过 Server酱 推送消息"""
    url = f"https://sctapi.ftqq.com/{token}.send"
    data = {
        "title": f"每日资讯简报 {datetime.now().strftime('%Y-%m-%d')}",
        "desp": content,
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        print(f"Server酱 推送响应: {resp.json()}")
    except Exception as e:
        print(f"Server酱 推送失败: {e}")

if __name__ == "__main__":
    print("MAIN ENTERED", flush=True)
    
    print("开始抓取半导体新闻（不限数量，每个源最多10条）...")
    semi_news = fetch_articles_from_sources(SEMI_RSS_FEEDS, limit_per_source=10)
    print(f"半导体新闻抓取到 {len(semi_news)} 条")
    
    print("开始抓取社会热点（至少10条）...")
    hot_news = fetch_articles_from_sources(HOT_RSS_FEEDS, limit_per_source=5, min_total=10)
    print(f"社会热点抓取到 {len(hot_news)} 条")
    
    if not semi_news and not hot_news:
        print("无新闻，退出")
        exit(0)
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：未设置 DEEPSEEK_API_KEY 环境变量")
        exit(1)
    
    print("调用DeepSeek生成摘要...")
    try:
        report = ask_deepseek(semi_news, hot_news, api_key)
        print("DeepSeek 返回成功")
    except Exception as e:
        print(f"DeepSeek API 调用失败: {e}")
        exit(1)
    
    # 打印报告到日志
    print("=== 生成的资讯简报 ===")
    print(report)
    print("=== 简报结束 ===")
    
    token = os.environ.get("PUSHPLUS_TOKEN")
    if token:
        send_wechat(report, token)
        print("已发送到微信")
    else:
        print("未设置 PUSHPLUS_TOKEN，仅打印报告")
