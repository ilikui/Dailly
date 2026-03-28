import os
import re
import json
import requests
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ========= RSS 订阅源（从 Cfg/rss.json 加载） =========
_script_dir = os.path.dirname(os.path.abspath(__file__))
RSS_CONFIG_PATH = os.path.join(os.path.dirname(_script_dir), "Cfg", "rss.json")

# ========= 关键词配置（逗号分隔，从 GitHub Secrets / 环境变量读取） =========
_kw_env = os.environ.get("KEYWORDS", "")
KEYWORDS = [k.strip() for k in _kw_env.split(",") if k.strip()]

# 北京时间
BJT = timezone(timedelta(hours=8))


# ========= 数据采集 =========
def load_rss_urls() -> list:
    """从 Cfg/rss.json 加载 RSS 源"""
    try:
        with open(RSS_CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
        
        # 支持两种格式：1) 数组格式  2) 对象格式 {type, name, url}
        if isinstance(config, list):
            urls = []
            for item in config:
                if isinstance(item, dict) and item.get("url"):
                    urls.append(item["url"])
            if urls:
                print(f"[INFO] 从 {RSS_CONFIG_PATH} 加载了 {len(urls)} 个 RSS 源")
                return urls
            else:
                raise ValueError(f"{RSS_CONFIG_PATH} 中没有有效的 URL")
        else:
            raise ValueError(f"{RSS_CONFIG_PATH} 格式不正确，应为数组")
    except Exception as e:
        print(f"[ERROR] 读取 {RSS_CONFIG_PATH} 失败: {e}")
        raise


def normalize_feed_url(url: str) -> str:
    """兼容带前缀标签的 URL（如 'News: http://...'），仅提取 http(s) 链接"""
    if not isinstance(url, str):
        return ""
    match = re.search(r"https?://\S+", url.strip())
    return match.group(0) if match else ""


def parse_json_feed(text: str) -> list:
    """解析 JSON Feed，统一输出 title/url/content_text 字段"""
    payload = json.loads(text)
    if not isinstance(payload, dict):
        return []

    items = payload.get("items", [])
    if not isinstance(items, list):
        return []

    parsed = []
    for item in items:
        if not isinstance(item, dict):
            continue
        parsed.append({
            "title": item.get("title", ""),
            "url": item.get("url", "") or item.get("external_url", ""),
            "content_text": item.get("content_text", "") or item.get("summary", ""),
        })
    return parsed


def parse_xml_feed(text: str) -> list:
    """解析 RSS/Atom XML，统一输出 title/url/content_text 字段"""
    root = ET.fromstring(text)
    parsed = []

    # RSS 2.0: <rss><channel><item>
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or item.findtext("summary") or "").strip()
        parsed.append({"title": title, "url": link, "content_text": description})

    # Atom: <feed><entry>
    if not parsed:
        for entry in root.findall(".//{*}entry"):
            title = (entry.findtext("{*}title") or "").strip()
            summary = (entry.findtext("{*}summary") or entry.findtext("{*}content") or "").strip()

            link = ""
            for link_node in entry.findall("{*}link"):
                href = (link_node.attrib.get("href") or "").strip()
                rel = (link_node.attrib.get("rel") or "alternate").strip()
                if href and rel in ("alternate", ""):
                    link = href
                    break
                if href and not link:
                    link = href

            parsed.append({"title": title, "url": link, "content_text": summary})

    return parsed


def fetch_feed(url: str) -> list:
    """拉取单个 RSS 源（支持 JSON Feed + RSS/Atom XML），返回统一 items 列表"""
    clean_url = normalize_feed_url(url)
    if not clean_url:
        print(f"[WARNING] 无效 RSS URL: {url}")
        return []

    try:
        resp = requests.get(clean_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # requests 默认对无 charset 的 text/* 回退到 ISO-8859-1，导致中文乱码
        # 用 apparent_encoding（chardet 检测）覆盖，保证 UTF-8/GBK 等正确解码
        if resp.encoding and resp.encoding.lower() == 'iso-8859-1':
            resp.encoding = resp.apparent_encoding or 'utf-8'
        content = resp.text.strip()
        if not content:
            print(f"[WARNING] 拉取 {clean_url} 返回空内容")
            return []

        # 先按 JSON 尝试，再回退 XML
        try:
            return parse_json_feed(content)
        except Exception:
            pass

        try:
            return parse_xml_feed(content)
        except Exception as e:
            print(f"[WARNING] 解析 {clean_url} 失败: {e}")
            return []
    except Exception as e:
        print(f"[WARNING] 拉取 {clean_url} 失败: {e}")
        return []


def fetch_all_feeds(rss_urls: list) -> list:
    """并发拉取所有 RSS 源，合并去重（以 url 字段为唯一键）"""
    all_items, seen = [], set()
    worker_count = min(max(len(rss_urls), 1), 20)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        feed_results = executor.map(fetch_feed, rss_urls)

    for items in feed_results:
        for item in items:
            item_url = item.get("url", "")
            if item_url and item_url not in seen:
                seen.add(item_url)
                all_items.append(item)

    return all_items


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


def append_daily_news(items: list):
    """按年/月目录保存抓取结果；同一天多次运行时向当天文件末尾追加一次快照"""
    now = datetime.now(BJT)
    date_str = now.strftime("%Y-%m-%d")
    archive_name = now.strftime("news_%Y_%m_%d.json")
    run_at = now.strftime("%Y-%m-%d %H:%M:%S")
    archive_dir = os.path.join("data", str(now.year), str(now.month))
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, archive_name)

    snapshot = {
        "run_at": run_at,
        "count": len(items),
        "items": [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content_text": item.get("content_text", ""),
            }
            for item in items
        ],
    }

    history = []
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                history = loaded
        except Exception as e:
            print(f"[WARNING] 读取 {archive_path} 失败，将重新创建: {e}")

    history.append(snapshot)

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"[INFO] 已追加保存当日数据: {archive_path} (第 {len(history)} 次运行, {len(items)} 条)")


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
def format_daily_report(items: list, keywords: list) -> str:
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

    # 0. 加载 RSS 源配置
    print("[INFO] 正在加载 RSS 源配置...")
    try:
        rss_urls = load_rss_urls()
        print(f"[INFO] 成功加载 {len(rss_urls)} 个 RSS 源")
    except Exception as e:
        print(f"[ERROR] 无法加载 RSS 源: {e}")
        exit(1)

    # 1. 拉取全部 RSS 数据
    print("[INFO] 正在拉取 RSS 数据...")
    all_items = fetch_all_feeds(rss_urls)
    print(f"[INFO] 共获取 {len(all_items)} 条新闻")

    # 2. 持久化热门新闻（给前端大屏使用）
    save_news(all_items, top_n=50)
    append_daily_news(all_items)

    # 3. 关键词过滤（KEYWORDS 未设置时推送全量新闻摘要）
    filtered = filter_by_keywords(all_items, KEYWORDS)
    print(f"[INFO] 关键词 {KEYWORDS} 过滤后: {len(filtered)} 条")

    # 4. 格式化日报（markdown_v2）并推送到企业微信
    report = format_daily_report(filtered if KEYWORDS else all_items, KEYWORDS)
    print(report)
    print(f"[INFO] 消息字节数: {len(report.encode('utf-8'))}")
    WeChatRobot(report)

    print("[INFO] ===== NewsFlow 完成 =====")
