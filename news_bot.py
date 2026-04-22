print("SCRIPT STARTED", flush=True)
import feedparser
import requests
import os
import json
from datetime import datetime, timezone, timedelta
import email.utils

# ---------- 日期处理 ----------
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
    if not date_obj:
        return False
    now = datetime.now(timezone.utc)
    if date_obj.tzinfo:
        date_utc = date_obj.astimezone(timezone.utc)
    else:
        date_utc = date_obj.replace(tzinfo=timezone.utc)
    return (now - date_utc).total_seconds() <= hours * 3600

# ---------- Bing 搜索 ----------
def fetch_bing_news(keywords, limit_per_keyword=6, recent_hours=48):
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
                    "summary": entry.get("summary", "")[:300],
                    "source": f"Bing-{kw}",
                    "published": pub_str
                })
        except Exception as e:
            print(f"Bing搜索失败 [{kw}]: {e}")
    return articles

# ========== 关键词配置 ==========
# 半导体：制造、技术、产业链、国际政策
SEMI_KEYWORDS = [
    "半导体制造", "芯片制造技术", "晶圆代工", "台积电 技术", "中芯国际 制程",
    "光刻机", "ASML 光刻", "半导体设备", "蚀刻机", "薄膜沉积",
    "第三代半导体", "碳化硅", "氮化镓", "功率半导体",
    "存储芯片 技术", "DRAM 技术", "NAND 闪存", "长江存储 技术",
    "Chiplet", "先进封装", "2.5D 封装", "3D 封装",
    "半导体材料", "硅片", "光刻胶", "电子特气",
    "半导体政策", "芯片法案", "美国 半导体 出口管制", "欧盟 芯片 法案",
    "日本 半导体 补贴", "韩国 半导体 政策", "中国 集成电路 政策",
    "半导体产业链", "芯片供应链", "汽车芯片 供应",
]

# 社会热点：政策类（国内+国际）
POLICY_KEYWORDS = [
    "中国 新政策", "国务院 政策", "发改委 新政", "工信部 发文",
    "科技创新 政策", "数字经济 政策", "新能源 政策", "环保 新政",
    "房地产 政策", "教育 改革", "医疗 改革", "社保 新规",
    "美国 新政策", "欧盟 法规", "国际贸易 政策", "一带一路",
]

# 国际战争/冲突（少量）
WAR_KEYWORDS = [
    "俄乌 局势", "巴以 冲突", "中东 局势", "红海 危机"
]

# ---------- DeepSeek 生成 ----------
def ask_deepseek(semi_articles, war_articles, policy_articles, api_key):
    prompt = f"""你是信息分析师。今天是{datetime.now(timezone.utc).strftime('%Y-%m-%d')}。
请根据以下新闻，生成一份【每日资讯简报】。

要求：
1. 先输出【半导体行业】板块（共{len(semi_articles)}条），聚焦制造技术、产业链市场、国际政策与环境。每条用一句话概括 + 原文链接，按重要性排序。
2. 然后输出【国际战争/冲突】板块（共{len(war_articles)}条），最多2条。
3. 最后输出【政策/社会热点】板块（共{len(policy_articles)}条），包括国内外重要政策、法规、经济改革等。每条一句话 + 链接。
4. 使用 Markdown 格式，标题为【每日资讯简报】。

--- 半导体行业 ---
"""
    for idx, art in enumerate(semi_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n--- 国际战争/冲突 ---\n"
    for idx, art in enumerate(war_articles[:2], 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n--- 政策/社会热点 ---\n"
    for idx, art in enumerate(policy_articles, 1):
        prompt += f"{idx}. {art['title']} | {art['summary']} | 链接：{art['link']}\n"
    prompt += "\n请直接输出，不要多余的解释。"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
    except Exception as e:
        raise Exception(f"DeepSeek 调用失败: {e}")

def send_wechat(content, token):
    url = f"https://sctapi.ftqq.com/{token}.send"
    data = {"title": f"每日资讯简报 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", "desp": content}
    try:
        resp = requests.post(url, data=data, timeout=10)
        print(f"Server酱 推送响应: {resp.json()}")
    except Exception as e:
        print(f"Server酱 推送失败: {e}")

if __name__ == "__main__":
    print("MAIN ENTERED", flush=True)
    
    print("抓取半导体新闻（制造/技术/政策）...")
    semi = fetch_bing_news(SEMI_KEYWORDS, limit_per_keyword=4, recent_hours=48)
    print(f"半导体新闻: {len(semi)} 条")
    
    print("抓取国际战争新闻...")
    war = fetch_bing_news(WAR_KEYWORDS, limit_per_keyword=2, recent_hours=72)
    print(f"战争新闻: {len(war)} 条")
    
    print("抓取政策/社会热点...")
    policy = fetch_bing_news(POLICY_KEYWORDS, limit_per_keyword=5, recent_hours=48)
    print(f"政策热点: {len(policy)} 条")
    
    if not semi and not war and not policy:
        print("无新闻，退出")
        exit(0)
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：未设置 DEEPSEEK_API_KEY")
        exit(1)
    
    print("调用 DeepSeek 生成简报...")
    try:
        report = ask_deepseek(semi, war, policy, api_key)
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
