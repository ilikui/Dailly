import os
import re
import json
import requests
from collections import Counter
from datetime import datetime, timezone, timedelta

# ========= RSS 订阅源 =========
RSS_URLS = [
    'https://www.buzzing.cc/feed.json',
    'https://hn.buzzing.cc/feed.json',
    'https://news.buzzing.cc/feed.json',
]

# ========= 关键词配置（逗号分隔，从 GitHub Secrets / 环境变量读取） =========
_kw_env = os.environ.get("KEYWORDS", "")
KEYWORDS = [k.strip() for k in _kw_env.split(",") if k.strip()]

# 北京时间
BJT = timezone(timedelta(hours=8))

# 停用词（英文）
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'is', 'are', 'was', 'were', 'be', 'been', 'by', 'from', 'with',
    'this', 'that', 'it', 'its', 'as', 'not', 'no', 'if', 'have', 'has',
    'do', 'does', 'did', 'how', 'what', 'why', 'when', 'who', 'which',
    'will', 'can', 'could', 'would', 'should', 'may', 'might', 'than',
    'into', 'about', 'after', 'before', 'up', 'out', 'more', 'new', 'he',
    'she', 'they', 'we', 'you', 'i', 'his', 'her', 'their', 'our', 'my',
    'your', 'also', 'over', 'just', 'us', 'all', 'had', 'so', 'then', 's',
}


# ========= 数据采集 =========
def fetch_feed(url: str) -> list:
    """拉取单个 RSS JSON Feed，返回 items 列表"""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        print(f"[WARNING] 拉取 {url} 失败: {e}")
        return []


def fetch_all_feeds() -> list:
    """拉取所有 RSS 源，合并去重（以 url 字段为唯一键）"""
    all_items, seen = [], set()
    for url in RSS_URLS:
        for item in fetch_feed(url):
            item_url = item.get("url", "")
            if item_url and item_url not in seen:
                seen.add(item_url)
                all_items.append(item)
    return all_items


# ========= 词频分析 =========
def word_frequency(items: list, top_n: int = 100) -> list:
    """对新闻标题进行词频统计，返回 [{name, value}] 列表（兼容 ECharts 词云格式）"""
    all_words = []
    for item in items:
        words = re.findall(r'[a-zA-Z]{3,}', item.get("title", ""))
        all_words.extend(w.lower() for w in words if w.lower() not in STOP_WORDS)
    counter = Counter(all_words)
    return [{"name": w, "value": cnt} for w, cnt in counter.most_common(top_n)]


def save_wordfreq(word_freq: list):
    """保存词频数据到 data/wordfreq.json，供前端大屏直接加载"""
    os.makedirs("data", exist_ok=True)
    with open("data/wordfreq.json", "w", encoding="utf-8") as f:
        json.dump(word_freq, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 词频数据已保存: data/wordfreq.json ({len(word_freq)} 词条)")


def save_news(items: list, top_n: int = 50):
    """保存 Top N 新闻到 data/news.json，供前端大屏热榜列表加载"""
    os.makedirs("data", exist_ok=True)
    news = [
        {"title": item.get("title", ""), "url": item.get("url", "")}
        for item in items[:top_n]
        if item.get("title")
    ]
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 新闻数据已保存: data/news.json ({len(news)} 条)")


# ========= 关键词过滤 =========
def filter_by_keywords(items: list, keywords: list) -> list:
    """按关键词过滤新闻条目（标题+摘要，不区分大小写）"""
    if not keywords:
        return items
    result = []
    for item in items:
        text = (item.get("title", "") + " " + item.get("content_text", "")).lower()
        if any(kw.lower() in text for kw in keywords):
            result.append(item)
    return result


# ========= 日报格式化 (markdown_v2) =========
def format_daily_report(items: list, word_freq: list, keywords: list) -> str:
    """格式化新闻日报，使用 markdown_v2 语法，控制在 4096 字节以内"""
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")

    # --- 头部 ---
    parts = [
        f"# NewsFlow 新闻日报",
        f"**{now} (BJT)**",
        "",
        "---",
        "",
    ]

    # --- 热词 ---
    if word_freq:
        hot_words = " ".join(f"`{w['name']}`" for w in word_freq[:10])
        parts += ["## 今日热词", "", hot_words, "", "---", ""]

    # --- 关键词过滤提示 ---
    if keywords:
        kw_str = " | ".join(f"**{k}**" for k in keywords)
        parts += ["## 关键词过滤", "", kw_str, "", "---", ""]

    # --- 新闻列表 ---
    parts += [f"## 今日新闻（共 {len(items)} 条）", ""]

    MAX_BYTES = 4000  # 留 96 字节给尾部
    header_bytes = len("\n".join(parts).encode("utf-8"))
    budget = MAX_BYTES - header_bytes

    news_lines = []
    for i, item in enumerate(items, 1):
        title = item.get("title", "无标题").replace("[", "（").replace("]", "）")
        url = item.get("url", "")
        if url:
            line = f"{i}. [{title}]({url})"
        else:
            line = f"{i}. {title}"
        line_bytes = len((line + "\n").encode("utf-8"))
        if budget - line_bytes < 0:
            news_lines.append(f"\n> *...还有 {len(items) - i + 1} 条未展示*")
            break
        news_lines.append(line)
        budget -= line_bytes

    parts += news_lines
    parts += ["", "---", "", "*数据来源: [buzzing.cc](https://www.buzzing.cc)*"]
    return "\n".join(parts)






# ========= 企业微信机器人 =========
def WeChatRobot(content: str):
    """以 markdown_v2 格式发送企业微信机器人 Webhook 消息"""
    # 优先读取环境变量；本地调试时可设置 WEBHOOK_KEY 环境变量，勿硬编码提交
    key = os.environ.get("WEBHOOK_KEY", "")
    if not key:
        print("[WARNING] 未设置 WEBHOOK_KEY，跳过微信推送")
        return None
    byte_len = len(content.encode("utf-8"))
    if byte_len > 4096:
        print(f"[WARNING] 消息内容 {byte_len} 字节超出 4096 上限，将被截断")
        content = content.encode("utf-8")[:4096].decode("utf-8", errors="ignore")
    apiurl = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown_v2",
        "markdown_v2": {
            "content": content
        }
    }
    response = requests.post(apiurl + key, headers=headers, json=data)
    records = response.json()
    print(f"[INFO] 微信机器人响应: {records}")
    return records


if __name__ == '__main__':
    print("[INFO] ===== NewsFlow 启动 =====")

    # 1. 拉取全部 RSS 数据
    print("[INFO] 正在拉取 RSS 数据...")
    all_items = fetch_all_feeds()
    print(f"[INFO] 共获取 {len(all_items)} 条新闻")

    # 2. 词频分析
    word_freq = word_frequency(all_items, top_n=100)
    print(f"[INFO] 词频 Top5: {[w['name'] for w in word_freq[:5]]}")

    # 3. 持久化词频数据 + 热门新闻（给前端大屏使用）
    save_wordfreq(word_freq)
    save_news(all_items, top_n=50)

    # 4. 关键词过滤（KEYWORDS 未设置时推送全量新闻摘要）
    filtered = filter_by_keywords(all_items, KEYWORDS)
    print(f"[INFO] 关键词 {KEYWORDS} 过滤后: {len(filtered)} 条")

    # 5. 格式化日报（markdown_v2）并推送到企业微信
    report = format_daily_report(filtered if KEYWORDS else all_items, word_freq, KEYWORDS)
    print(report)
    print(f"[INFO] 消息字节数: {len(report.encode('utf-8'))}")
    WeChatRobot(report)

    print("[INFO] ===== NewsFlow 完成 =====")
