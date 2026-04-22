print("SCRIPT STARTED", flush=True)
import feedparser
import requests
import os
import json
from datetime import datetime
from collections import OrderedDict

# ---------- 半导体行业 RSS 源（每个源取 10 条）----------
# 半导体行业 RSS 源（含 Bing 搜索 + 已知可用源）
SEMI_RSS_FEEDS = [
    "https://wallstreetcn.com/news/rss",                # 华尔街见闻
    "https://www.36kr.com/feed",                        # 36氪
    "https://www.ithome.com/rss/",                      # IT之家
    "https://www.bing.com/news/search?q=中芯国际&format=rss",
    "https://www.bing.com/news/search?q=龙芯&format=rss",
    "https://www.bing.com/news/search?q=长江存储&format=rss",
    "https://www.bing.com/news/search?q=国产CPU&format=rss",
    "https://www.bing.com/news/search?q=国产存储&format=rss",
    "https://www.bing.com/news/search?q=半导体+制造+中国&format=rss",
]

# 国际战争/冲突（仍用之前能抓到8条的那些，比如 BBC）
WAR_RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",       # BBC 世界新闻
]

# 国内社会热点（暂时只用 Bing 搜索国内热点关键词）
DOMESTIC_RSS_FEEDS = [
    "https://www.bing.com/news/search?q=中国+社会+热点&format=rss",
    "https://www.bing.com/news/search?q=国内+新闻&format=rss",
]

# 生活相关（同样用 Bing 搜索）
LIFE_RSS_FEEDS = [
    "https://www.bing.com/news/search?q=生活+健康&format=rss",
    "https://www.bing.com/news/search?q=科技+生活&format=rss",
]
def fetch_articles_from_sources(rss_list, limit_per_source=10):
    """抓取新闻，返回去重后的列表（基于标题去重）"""
    articles = []
    seen_titles = set()
    for url in rss_list:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:limit_per_source]:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                articles.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:200],
                    "source": feed.feed.get("title", url),
                    "published": entry.get("published", "")
                })
        except Exception as e:
            print(f"抓取失败 {url}: {e}")
    return articles

def ask_deepseek(semi_articles, war_articles, domestic_articles, life_articles, api_key):
    """调用 DeepSeek 生成早报，分四个板块"""
    prompt = f"""你是信息分析师。今天是{datetime.now().strftime('%Y-%m-%d')}。
请根据以下新闻，生成一份【每日资讯简报】。

要求：
1. 先输出【半导体行业】板块（共{len(semi_articles)}条），每条用一句话概括 + 原文链接，按重要性排序。
2. 然后输出【国际战争/冲突】板块（共{len(war_articles)}条），每条一句话 + 链接。
3. 接着输出【国内社会热点】板块（共{len(domestic_articles)}条），每条一句话 + 链接。
4. 最后输出【生活相关】板块（共{len(life_articles)}条），每条一句话 + 链接。
5. 整体使用 Markdown 格式，标题为【每日资讯简报】。

--- 半导体行业新闻 ---
"""
    for idx, art in enumerate(semi_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n--- 国际战争/冲突 ---\n"
    for idx, art in enumerate(war_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n--- 国内社会热点 ---\n"
    for idx, art in enumerate(domestic_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n--- 生活相关 ---\n"
    for idx, art in enumerate(life_articles, 1):
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
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            raise Exception(f"API错误: {data['error']}")
        else:
            raise Exception(f"未知响应格式: {data}")
    except requests.exceptions.Timeout:
        raise Exception("DeepSeek API 请求超时（120秒）")
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
    
    print("开始抓取半导体新闻...")
    semi_news = fetch_articles_from_sources(SEMI_RSS_FEEDS, limit_per_source=10)
    print(f"半导体新闻抓取到 {len(semi_news)} 条")
    
    print("开始抓取国际战争/冲突...")
    war_news = fetch_articles_from_sources(WAR_RSS_FEEDS, limit_per_source=8)
    print(f"战争新闻抓取到 {len(war_news)} 条")
    
    print("开始抓取国内社会热点...")
    domestic_news = fetch_articles_from_sources(DOMESTIC_RSS_FEEDS, limit_per_source=8)
    print(f"国内热点抓取到 {len(domestic_news)} 条")
    
    print("开始抓取生活相关...")
    life_news = fetch_articles_from_sources(LIFE_RSS_FEEDS, limit_per_source=6)
    print(f"生活新闻抓取到 {len(life_news)} 条")
    
    if not semi_news and not war_news and not domestic_news and not life_news:
        print("无新闻，退出")
        exit(0)
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：未设置 DEEPSEEK_API_KEY 环境变量")
        exit(1)
    
    print("调用DeepSeek生成摘要...")
    try:
        report = ask_deepseek(semi_news, war_news, domestic_news, life_news, api_key)
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
