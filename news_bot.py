print("SCRIPT STARTED", flush=True)
import feedparser
import requests
import os
import json
from datetime import datetime, timezone, timedelta
import email.utils
from collections import OrderedDict

# ---------- 日期处理函数 ----------
def parse_rfc2822_date(date_str):
    if not date_str:
        return None
    try:
        return datetime(*email.utils.parsedate(date_str)[:6], tzinfo=timezone.utc)
    except:
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None

def is_recent(date_obj, hours=48):
    """判断新闻是否在最近 hours 小时内（默认48小时）"""
    if not date_obj:
        return False
    now = datetime.now(timezone.utc)
    if date_obj.tzinfo:
        date_utc = date_obj.astimezone(timezone.utc)
    else:
        date_utc = date_obj.replace(tzinfo=timezone.utc)
    delta = now - date_utc
    return delta.total_seconds() <= hours * 3600

# ---------- Bing 新闻搜索 ----------
def fetch_bing_news(keywords, limit_per_keyword=8, recent_hours=48):
    """
    从 Bing 新闻搜索 RSS 抓取新闻。
    keywords: 关键词列表
    limit_per_keyword: 每个关键词最多取多少条
    recent_hours: 只保留最近多少小时内的新闻（默认48小时，保证有内容）
    """
    articles = []
    seen_titles = set()
    for kw in keywords:
        url = f"https://www.bing.com/news/search?q={kw}&format=rss"
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:limit_per_keyword]:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue
                pub_str = entry.get("published", "") or entry.get("pubDate", "")
                pub_date = parse_rfc2822_date(pub_str)
                if not is_recent(pub_date, recent_hours):
                    continue
                seen_titles.add(title)
                articles.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:200],
                    "source": f"Bing-{kw}",
                    "published": pub_str
                })
        except Exception as e:
            print(f"Bing搜索失败 [{kw}]: {e}")
    return articles

# ---------- 关键词配置（大幅扩充）----------
# 半导体行业（制造、芯片、存储、通信设备等）—— 确保每天都有大量新闻
SEMI_KEYWORDS = [
    "半导体", "芯片", "集成电路", "晶圆", "光刻机", "ASML", "台积电", "中芯国际",
    "华虹半导体", "长江存储", "长鑫存储", "龙芯", "兆芯", "海光", "飞腾",
    "国产CPU", "国产GPU", "AI芯片", "存储芯片", "闪存", "DRAM", "NAND",
    "半导体设备", "北方华创", "中微公司", "半导体材料", "硅片", "光刻胶",
    "第三代半导体", "碳化硅", "氮化镓", "功率半导体", "IGBT", "MOSFET",
    "通信芯片", "5G芯片", "物联网芯片", "射频芯片", "模拟芯片",
    "封装测试", "先进封装", "Chiplet", "RISC-V", "ARM", "x86",
    "英特尔", "AMD", "英伟达", "高通", "联发科", "三星半导体", "SK海力士",
    "美光", "德州仪器", "意法半导体", "恩智浦", "Infineon"
]

# 国际战争/冲突（少量）
WAR_KEYWORDS = [
    "俄乌战争", "巴以冲突", "中东局势", "也门胡塞", "红海危机", "国际冲突"
]

# 国内社会热点（增加具体事件类关键词）
DOMESTIC_KEYWORDS = [
    "国内热点", "中国社会新闻", "民生热点", "政策新规", "经济数据", "房地产",
    "教育新闻", "医疗改革", "环保督察", "乡村振兴", "科技创新", "中国航天",
    "法治新闻", "突发事件", "交通", "天气预警"
]

# 生活相关
LIFE_KEYWORDS = [
    "健康养生", "食品安全", "科技生活", "数码产品", "手机", "新能源汽车",
    "旅游", "美食", "健身", "心理健康", "育儿", "老年生活"
]

# ---------- DeepSeek 生成简报 ----------
def ask_deepseek(semi_articles, war_articles, domestic_articles, life_articles, api_key):
    prompt = f"""你是信息分析师。今天是{datetime.now(timezone.utc).strftime('%Y-%m-%d')}。
请根据以下新闻，生成一份【每日资讯简报】。

要求：
1. 先输出【半导体行业】板块（共{len(semi_articles)}条），每条用一句话概括 + 原文链接，按重要性排序。
2. 然后输出【国际战争/冲突】板块（共{len(war_articles)}条），最多保留2条最重要的，每条一句话 + 链接。
3. 接着输出【国内社会热点】板块（共{len(domestic_articles)}条），每条一句话 + 链接。
4. 最后输出【生活相关】板块（共{len(life_articles)}条），每条一句话 + 链接。
5. 整体使用 Markdown 格式，标题为【每日资讯简报】。

--- 半导体行业新闻 ---
"""
    for idx, art in enumerate(semi_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n--- 国际战争/冲突 ---\n"
    for idx, art in enumerate(war_articles[:2], 1):
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
    url = f"https://sctapi.ftqq.com/{token}.send"
    data = {
        "title": f"每日资讯简报 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "desp": content,
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        print(f"Server酱 推送响应: {resp.json()}")
    except Exception as e:
        print(f"Server酱 推送失败: {e}")

# ---------- 主程序 ----------
if __name__ == "__main__":
    print("MAIN ENTERED", flush=True)
    
    print("正在从 Bing 搜索半导体新闻（扩充关键词）...")
    semi_news = fetch_bing_news(SEMI_KEYWORDS, limit_per_keyword=5, recent_hours=48)
    print(f"半导体新闻抓取到 {len(semi_news)} 条（最近48小时）")
    
    print("正在从 Bing 搜索国际战争新闻...")
    war_news = fetch_bing_news(WAR_KEYWORDS, limit_per_keyword=3, recent_hours=48)
    print(f"战争新闻抓取到 {len(war_news)} 条")
    
    print("正在从 Bing 搜索国内社会热点...")
    domestic_news = fetch_bing_news(DOMESTIC_KEYWORDS, limit_per_keyword=4, recent_hours=48)
    print(f"国内热点抓取到 {len(domestic_news)} 条")
    
    print("正在从 Bing 搜索生活相关...")
    life_news = fetch_bing_news(LIFE_KEYWORDS, limit_per_keyword=3, recent_hours=48)
    print(f"生活新闻抓取到 {len(life_news)} 条")
    
    if not semi_news and not war_news and not domestic_news and not life_news:
        print("未抓到任何新闻，退出")
        exit(0)
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：未设置 DEEPSEEK_API_KEY")
        exit(1)
    
    print("调用 DeepSeek 生成简报...")
    try:
        report = ask_deepseek(semi_news, war_news, domestic_news, life_news, api_key)
        print("DeepSeek 返回成功")
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        exit(1)
    
    print("=== 生成的简报 ===")
    print(report)
    print("=== 简报结束 ===")
    
    token = os.environ.get("PUSHPLUS_TOKEN")
    if token:
        send_wechat(report, token)
        print("已推送到微信")
    else:
        print("未设置 PUSHPLUS_TOKEN，仅打印")
