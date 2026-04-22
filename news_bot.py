print("SCRIPT STARTED", flush=True)
import feedparser
import requests
import os
import json
from datetime import datetime
from collections import OrderedDict

# ---------- 半导体行业 RSS 源（每个源取 10 条）----------
SEMI_RSS_FEEDS = [
    # 中文半导体媒体
    "https://www.semiinsights.com/feed",          # 半导体行业观察
    "https://www.jiweicn.com/rss",                # 集微网
    "https://www.eet-china.com/feed",             # EET电子工程专辑
    "https://www.21ic.com/rss.xml",               # 21ic中国电子网
    "https://www.elecfans.com/rss.xml",           # 电子发烧友
    "https://www.eeworld.com.cn/rss/news",        # EEWorld电子工程世界
    # 国内厂商官方新闻
    "https://www.loongson.cn/rss",                # 龙芯中科
    "https://www.ymtc.com/rss",                   # 长江存储
    "https://www.smics.com/rss",                  # 中芯国际
    "https://www.verisilicon.com/rss",            # 芯原股份
    "https://www.idcquan.com/index/index_1.shtml/rss",            # IDC快讯
    "https://www.toutiao.com/?channel=tech&source=ch/rss",            #  今日头条
    # 国际但中文内容
    "https://www.eetimes.com/feed",               # EE Times
    "https://semiengineering.com/feed",           # Semiconductor Engineering
    "https://wallstreetcn.com/news/rss",          # 华尔街见闻
]

# ---------- 社会热点 RSS 源（分三类：战争/国际冲突、国内社会、生活）----------
WAR_RSS_FEEDS = [
    "http://feeds.reuters.com/reuters/worldNews",          # 路透国际（含战争）
    "http://feeds.bbci.co.uk/news/world/rss.xml",          # BBC 世界
    "https://www.aljazeera.com/xml/rss/news.xml",          # 半岛电视台
    "https://www.defensenews.com/arc/outboundfeeds/rss/",  # Defense News
    "https://www.globaltimes.cn/rss/world.xml",            # 环球时报国际
]
DOMESTIC_RSS_FEEDS = [
    "http://rss.caixin.com/rollnews.xml",                  # 财新网
    "https://www.thepaper.cn/rss_news.xml",                # 澎湃新闻
    "http://www.people.com.cn/rss/people.xml",             # 人民网
    "https://www.guancha.cn/index.rss",                    # 观察者网
    "http://news.cctv.com/xml/news.xml",                   # 央视新闻
]
LIFE_RSS_FEEDS = [
    "https://www.zhihu.com/rss",                           # 知乎（生活/热门）
    "https://www.guokr.com/rss/",                          # 果壳网（生活科普）
    "https://www.xiachufang.com/feed/",                    # 下厨房（美食生活）
    "https://www.healthday.com/rss/",                      # 健康新闻
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
