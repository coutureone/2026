import argparse
import base64
import hashlib
import hmac
import random
import re
import sqlite3
import tempfile
import time
import urllib.parse

import pendulum
import requests
import telebot
from github import Github, Auth
from opencc import OpenCC
from telegramify_markdown import markdownify

# 1 real get up #5 for test
GET_UP_ISSUE_NUMBER = 1
GET_UP_MESSAGE_TEMPLATE = """今天的起床时间是--{get_up_time}。

起床啦。

今天是今年的第 {day_of_year} 天。

{year_progress}

{github_activity}

{running_info}

{history_today}

{street_view}

今天的一首诗:

{sentence}
"""

# 使用 v2 API 获取完整诗词
SENTENCE_API = "https://v2.jinrishici.com/one.json"

DEFAULT_SENTENCE = """《回乡偶书》  
少小离家老大回，  
乡音无改鬓毛衰。  
儿童相见不相识，  
笑问客从何处来。  

—— 唐·贺知章"""
TIMEZONE = "Asia/Shanghai"

# 你的出生年份，用于计算年龄
BIRTH_YEAR = 1999  # 请修改为你的实际出生年份

# 当无法获取历史事件时的备用有趣内容
FALLBACK_INTERESTING_FACTS = [
    "🎲 今天是个特别的日子，因为你又活过了新的一天！",
    "💡 有趣的事实：每天地球上大约会发生 50,000 次地震，但大多数我们感觉不到。",
    "🌍 你知道吗？地球每天会被大约 100 吨的宇宙尘埃撞击。",
    "⏰ 时间小知识：一天并不是精确的 24 小时，而是 23 小时 56 分 4 秒。",
    "🧠 大脑趣闻：你的大脑每天产生大约 50,000 个想法。",
    "📚 阅读启示：平均每人每天会说大约 16,000 个字。",
    "☕ 咖啡因事实：全世界每天要喝掉超过 20 亿杯咖啡。",
    "🌟 宇宙奥秘：光从太阳到达地球需要约 8 分 20 秒。",
    "💭 哲学思考：'今天'这个词在不同时区有 24 种不同的含义。",
    "🎯 激励语录：每一个伟大的成就，都始于决定去尝试。",
]

# 初始化繁简转换器
cc = OpenCC('t2s')  # 繁体转简体


def convert(text, _target='zh-cn'):
    """繁体转简体"""
    return cc.convert(text)


def verify_dingtalk_signature(secret):
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode("utf-8")
    string_to_sign = "{}\n{}".format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(
        secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def send_dingtalk_message(webhook, secret, content):
    url = webhook
    if secret:
        timestamp, sign = verify_dingtalk_signature(secret)
        url = f"{webhook}&timestamp={timestamp}&sign={sign}"

    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": "早起打卡",
            "text": content
        }
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        if r.status_code == 200 and r.json().get("errcode") == 0:
            print("DingTalk message sent successfully")
        else:
            print(f"DingTalk error: {r.text}")
    except Exception as e:
        print(f"DingTalk send failed: {e}")


def login(token):
    return Github(auth=Auth.Token(token))


def get_one_sentence():
    """获取今天的一首诗

    使用今日诗词 v2 API 获取完整的诗词内容
    返回格式：《诗名》\n诗词内容\n\n—— 朝代·作者
    """
    try:
        r = requests.get(SENTENCE_API, timeout=10)
        if r.ok:
            data = r.json()

            # 获取诗词来源信息
            origin = data.get("data", {}).get("origin", {})
            title = origin.get("title", "")
            dynasty = origin.get("dynasty", "")
            author = origin.get("author", "")
            content_list = origin.get("content", [])

            if content_list and title and author:
                # 将诗词内容数组合并为字符串（每句一行，行尾加两个空格兼容钉钉Markdown换行）
                content = "  \n".join(content_list)
                # 格式化输出：《诗名》\n\n内容\n\n—— 朝代·作者
                poem = f"《{title}》  \n{content}  \n\n—— {dynasty}·{author}"
                return poem

        return DEFAULT_SENTENCE
    except Exception as e:
        print(f"get SENTENCE_API wrong: {e}")
        return DEFAULT_SENTENCE


def get_random_street_view():
    """获取今天的随机街景

    使用 RandomStreetView 网站，每次访问都会显示一个随机的街景位置

    Returns:
        str: 格式化的街景信息，失败时返回空字符串
    """
    try:
        # 使用 randomstreetview.com，每次点击都会随机显示该国家/地区的街景
        sites = [
            ("🇯🇵 日本", "https://randomstreetview.com/#jpn"),
            ("🇮🇹 意大利", "https://randomstreetview.com/#ita"),
            ("🇫🇷 法国", "https://randomstreetview.com/#fra"),
            ("🇬🇧 英国", "https://randomstreetview.com/#gbr"),
            ("🇺🇸 美国", "https://randomstreetview.com/#usa"),
            ("🇦🇺 澳大利亚", "https://randomstreetview.com/#aus"),
            ("🇧🇷 巴西", "https://randomstreetview.com/#bra"),
            ("🇿🇦 南非", "https://randomstreetview.com/#zaf"),
            ("🇹🇭 泰国", "https://randomstreetview.com/#tha"),
            ("🇲🇽 墨西哥", "https://randomstreetview.com/#mex"),
            ("🇪🇸 西班牙", "https://randomstreetview.com/#esp"),
            ("🇩🇪 德国", "https://randomstreetview.com/#deu"),
            ("🇵🇹 葡萄牙", "https://randomstreetview.com/#prt"),
            ("🇳🇴 挪威", "https://randomstreetview.com/#nor"),
            ("🇸🇪 瑞典", "https://randomstreetview.com/#swe"),
            ("🇫🇮 芬兰", "https://randomstreetview.com/#fin"),
            ("🇵🇱 波兰", "https://randomstreetview.com/#pol"),
            ("🇨🇿 捷克", "https://randomstreetview.com/#cze"),
            ("🇬🇷 希腊", "https://randomstreetview.com/#grc"),
            ("🇹🇷 土耳其", "https://randomstreetview.com/#tur"),
            ("🇷🇺 俄罗斯", "https://randomstreetview.com/#rus"),
            ("🇦🇷 阿根廷", "https://randomstreetview.com/#arg"),
            ("🇨🇱 智利", "https://randomstreetview.com/#chl"),
            ("🇨🇴 哥伦比亚", "https://randomstreetview.com/#col"),
            ("🇵🇪 秘鲁", "https://randomstreetview.com/#per"),
            ("🇮🇩 印尼", "https://randomstreetview.com/#idn"),
            ("🇲🇾 马来西亚", "https://randomstreetview.com/#mys"),
            ("🇸🇬 新加坡", "https://randomstreetview.com/#sgp"),
            ("🇵🇭 菲律宾", "https://randomstreetview.com/#phl"),
            ("🇹🇼 台湾", "https://randomstreetview.com/#twn"),
            ("🇭🇰 香港", "https://randomstreetview.com/#hkg"),
            ("🇰🇷 韩国", "https://randomstreetview.com/#kor"),
            ("🇮🇱 以色列", "https://randomstreetview.com/#isr"),
            ("🇦🇪 阿联酋", "https://randomstreetview.com/#are"),
            ("🇮🇪 爱尔兰", "https://randomstreetview.com/#irl"),
            ("🇳🇱 荷兰", "https://randomstreetview.com/#nld"),
            ("🇧🇪 比利时", "https://randomstreetview.com/#bel"),
            ("🇨🇭 瑞士", "https://randomstreetview.com/#che"),
            ("🇦🇹 奥地利", "https://randomstreetview.com/#aut"),
            ("🌍 全球随机", "https://randomstreetview.com/"),
        ]

        # 用日期作为种子，确保同一天显示同一个地点
        now = pendulum.now(TIMEZONE)
        day_seed = now.year * 1000 + now.day_of_year
        random.seed(day_seed)
        name, url = random.choice(sites)
        random.seed()  # 重置随机种子，不影响其他随机调用

        return f"""今日街景：{name}

[开始随机街景之旅]({url})"""
    except Exception as e:
        print(f"Error getting random street view: {e}")
        return ""


def get_history_today_from_baidu(birth_year=BIRTH_YEAR, limit=3):
    """从百度百科获取历史上的今天

    Args:
        birth_year: 出生年份，用于计算年龄
        limit: 返回事件数量限制

    Returns:
        list: 事件列表，每个事件为 dict {'year': int, 'text': str}
    """
    try:
        now = pendulum.now(TIMEZONE)
        month = now.format("MM")
        day = now.format("DD")

        # 百度百科历史上的今天 API
        url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{month}.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            return []

        data = response.json()
        # 数据格式: {"01": {"0106": [{"year": "1999年", "title": "...", "desc": "..."}]}}
        month_data = data.get(month, {})
        day_key = f"{month}{day}"
        events_raw = month_data.get(day_key, [])

        events = []
        for event in events_raw:
            year_str = event.get("year", "")
            # 提取年份数字，支持 "1999年" 或 "公元前200年" 格式
            year_match = None
            if "公元前" in year_str:
                import re
                match = re.search(r"公元前(\d+)", year_str)
                if match:
                    year_match = -int(match.group(1))
            else:
                import re
                match = re.search(r"(\d+)", year_str)
                if match:
                    year_match = int(match.group(1))

            if year_match is not None:
                text = event.get("title", "") or event.get("desc", "")
                # 清理HTML标签
                text = re.sub(r'<[^>]+>', '', text)
                events.append({"year": year_match, "text": text})

        return events

    except Exception as e:
        print(f"Error getting history from Baidu: {e}")
        return []


def get_history_today_from_wikimedia(birth_year=BIRTH_YEAR, limit=3):
    """从 Wikimedia 获取历史上的今天

    Args:
        birth_year: 出生年份，用于计算年龄
        limit: 返回事件数量限制

    Returns:
        list: 事件列表，每个事件为 dict {'year': int, 'text': str, 'wiki_url': str}
    """
    try:
        now = pendulum.now(TIMEZONE)
        month = now.format("MM")
        day = now.format("DD")

        # Wikimedia On this day API
        url = f"https://api.wikimedia.org/feed/v1/wikipedia/zh/onthisday/events/{month}/{day}"
        headers = {
            "User-Agent": "GetUpBot/1.0 (https://github.com/coutureone/2026)",
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            print(f"Wikimedia API failed: {response.status_code}")
            return []

        data = response.json()
        events_raw = data.get("events", [])

        events = []
        for event in events_raw:
            year = event.get("year")
            text = event.get("text", "")
            wiki_url = ""
            pages = event.get("pages", [])
            if pages:
                content_urls = pages[0].get("content_urls", {})
                desktop = content_urls.get("desktop", {})
                wiki_url = desktop.get("page", "")

            if year:
                events.append({"year": year, "text": text, "wiki_url": wiki_url})

        return events

    except Exception as e:
        print(f"Error getting history from Wikimedia: {e}")
        return []


def get_history_today(birth_year=BIRTH_YEAR, limit=3):
    """获取历史上的今天发生的事件

    优先使用 Wikimedia API，失败时使用百度百科 API 作为备选

    Args:
        birth_year: 出生年份，用于计算年龄
        limit: 返回事件数量限制

    Returns:
        str: 格式化的历史事件信息
    """
    try:
        now = pendulum.now(TIMEZONE)
        current_year = now.year

        # 先尝试 Wikimedia API
        events = get_history_today_from_wikimedia(birth_year, limit)

        # 如果 Wikimedia 失败，尝试百度 API
        if not events:
            events = get_history_today_from_baidu(birth_year, limit)

        if not events:
            return random.choice(FALLBACK_INTERESTING_FACTS)

        # 过滤出 birth_year 年到现在的事件
        filtered_events = [
            event
            for event in events
            if birth_year <= event["year"] <= current_year
        ]

        # 如果没有符合条件的事件，就取所有正数年份的事件
        if not filtered_events:
            filtered_events = [e for e in events if e["year"] > 0]

        if not filtered_events:
            return random.choice(FALLBACK_INTERESTING_FACTS)

        # 随机选择指定数量的事件
        selected_events = random.sample(
            filtered_events, min(limit, len(filtered_events))
        )
        # 按年份倒序排列选中的事件
        selected_events.sort(key=lambda x: x.get("year", 0), reverse=True)

        result_lines = []

        for event in selected_events:
            year = event.get("year")
            text = event.get("text", "")
            wiki_url = event.get("wiki_url", "")

            # 计算当时的年龄
            if year and year >= birth_year:
                age = year - birth_year
                age_text = f"（那年我 {age} 岁）"
            elif year and year < birth_year:
                years_before = birth_year - year
                age_text = f"（我出生前 {years_before} 年）"
            else:
                age_text = ""

            # 清理文本中的换行符和多余空格，并转换为简体中文
            text = text.replace("\n", " ").strip()
            text = convert(text, "zh-cn")  # 繁体转简体

            # 构建带链接的文本
            # 行尾加两个空格兼容钉钉Markdown换行
            if wiki_url:
                result_lines.append(f"• **{year}年**：[{text}]({wiki_url}) {age_text}  ")
            else:
                result_lines.append(f"• **{year}年**：{text} {age_text}  ")

        return "历史上的今天：\n\n" + "\n".join(result_lines)

    except Exception as e:
        print(f"Error getting history today: {e}")
        # 返回随机的有趣内容作为备用
        return random.choice(FALLBACK_INTERESTING_FACTS)


def _get_repo_name_from_url(url):
    """从仓库 URL 中提取仓库名称"""
    return "/".join(url.split("/")[-2:])


def _make_api_request(url, headers, params=None):
    """统一的 API 请求函数"""
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"API 请求失败: {response.status_code}"
    except Exception as e:
        return None, f"请求出错: {e}"


def _process_search_items(items, username, item_type):
    """处理搜索结果（PR 或 Issue）"""
    activities = []
    action_text = "创建了 PR" if item_type == "pr" else "创建了 Issue"

    for item in items:
        if item["user"]["login"] == username:
            repo_name = _get_repo_name_from_url(item["repository_url"])
            title = item["title"]
            url = item["html_url"]
            activities.append(f"{action_text}: [{title}]({url}) ({repo_name})")

    return activities


def _process_events(events, yesterday_start, yesterday_end):
    """处理用户事件"""
    activities = []

    for event in events[:100]:
        event_created = pendulum.parse(event["created_at"])

        if event_created < yesterday_start:
            break

        if not (yesterday_start <= event_created <= yesterday_end):
            continue

        if not event.get("public", True):
            continue

        event_type = event["type"]
        repo_name = event["repo"]["name"]

        if event_type == "PullRequestEvent":
            action = event["payload"].get("action")
            if action == "merged":
                pr_data = event["payload"]["pull_request"]
                activities.append(
                    f"合并了 PR: [{pr_data['title']}]({pr_data['html_url']}) ({repo_name})"
                )
        elif event_type == "IssuesEvent":
            action = event["payload"].get("action")
            if action == "closed":
                issue_data = event["payload"]["issue"]
                activities.append(
                    f"关闭了 Issue: [{issue_data['title']}]({issue_data['html_url']}) ({repo_name})"
                )
        elif event_type == "WatchEvent":
            action = event["payload"].get("action")
            if action == "started":
                repo_url = f"https://github.com/{repo_name}"
                activities.append(f"Star 了项目: [{repo_name}]({repo_url})")

    return activities


def get_yesterday_github_activity(github_token=None, username="coutureone"):
    """获取昨天的 GitHub 活动"""
    try:
        # 时间设置
        yesterday = pendulum.now(TIMEZONE).subtract(days=1)
        yesterday_start = yesterday.start_of("day").in_timezone("UTC")
        yesterday_end = yesterday.end_of("day").in_timezone("UTC")
        yesterday_date = yesterday.format("YYYY-MM-DD")

        # 请求头设置
        headers = {}
        if github_token:
            headers.update(
                {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                }
            )

        activities = []

        # 获取创建的 PR
        search_url = "https://api.github.com/search/issues"
        pr_query = f"is:pr is:public author:{username} created:{yesterday_date}"
        print(f"PR 搜索查询: {pr_query}")
        pr_data, error = _make_api_request(
            search_url,
            headers,
            {
                "q": pr_query,
                "per_page": 100,
            },
        )
        if pr_data:
            pr_items = pr_data.get("items", [])
            print(f"找到 {len(pr_items)} 个 PR")
            pr_activities = _process_search_items(pr_items, username, "pr")
            print(f"处理后的 PR 活动: {pr_activities}")
            activities.extend(pr_activities)
        elif error:
            print(f"搜索 PR 时出错: {error}")

        # 获取创建的 Issue
        issue_query = f"is:issue is:public author:{username} created:{yesterday_date}"
        print(f"Issue 搜索查询: {issue_query}")
        issue_data, error = _make_api_request(
            search_url,
            headers,
            {
                "q": issue_query,
                "per_page": 100,
            },
        )
        if issue_data:
            issue_items = issue_data.get("items", [])
            print(f"找到 {len(issue_items)} 个 Issue")
            issue_activities = _process_search_items(issue_items, username, "issue")
            print(f"处理后的 Issue 活动: {issue_activities}")
            activities.extend(issue_activities)
        elif error:
            print(f"搜索 Issue 时出错: {error}")

        # 获取其他事件（合并、关闭、Star 等）
        # 检查多页事件，因为 Star 事件可能不在第一页
        events_url = f"https://api.github.com/users/{username}/events"
        all_activities = []

        for page in range(1, 4):  # 检查前3页，总共约90个事件
            page_params = {"page": page, "per_page": 30}
            events_data, error = _make_api_request(events_url, headers, page_params)

            if error:
                print(f"获取第 {page} 页 Events 时出错: {error}")
                continue

            if not events_data:
                break  # 没有更多事件了

            page_activities = _process_events(
                events_data, yesterday_start, yesterday_end
            )
            all_activities.extend(page_activities)

            # 如果这一页事件数少于30，说明已经到底了
            if len(events_data) < 30:
                break

        activities.extend(all_activities)

        # 返回结果
        print(f"所有活动总数: {len(activities)}")
        print(f"所有活动: {activities}")
        if activities:
            # 去重并限制数量
            unique_activities = list(dict.fromkeys(activities))
            print(f"去重后活动数: {len(unique_activities)}")
            result = "GitHub：\n\n" + "\n".join(
                f"• {activity}" for activity in unique_activities[:15]
            )
            print(f"最终结果:\n{result}")
            return result

        return ""

    except Exception as e:
        print(f"Error getting GitHub activity: {e}")
        return ""


def get_running_distance():
    try:
        url = "https://raw.githubusercontent.com/coutureone/running/master/run_page/data.db"
        response = requests.get(url)

        if not response.ok:
            return ""

        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(response.content)
            temp_file.flush()

            with sqlite3.connect(temp_file.name) as conn:
                cursor = conn.cursor()
                now = pendulum.now(TIMEZONE)
                yesterday = now.subtract(days=1)
                month_start = now.start_of("month")
                year_start = now.start_of("year")

                yesterday_query = f"""
                SELECT 
                    COUNT(*) as count,
                    ROUND(SUM(distance)/1000, 2) as total_km
                FROM activities
                WHERE DATE(start_date_local) = '{yesterday.to_date_string()}'
                """

                month_query = f"""
                SELECT 
                    COUNT(*) as count,
                    ROUND(SUM(distance)/1000, 2) as total_km
                FROM activities
                WHERE DATE(start_date_local) >= '{month_start.to_date_string()}' 
                    AND DATE(start_date_local) < '{now.add(days=1).to_date_string()}'
                """

                year_query = f"""
                SELECT 
                    COUNT(*) as count,
                    ROUND(SUM(distance)/1000, 2) as total_km
                FROM activities
                WHERE DATE(start_date_local) >= '{year_start.to_date_string()}' 
                    AND DATE(start_date_local) < '{now.add(days=1).to_date_string()}'
                """

                yesterday_result = cursor.execute(yesterday_query).fetchone()
                month_result = cursor.execute(month_query).fetchone()
                year_result = cursor.execute(year_query).fetchone()

            running_info_parts = []

            if yesterday_result and yesterday_result[0] > 0:
                running_info_parts.append(f"• 昨天跑了 {yesterday_result[1]} 公里")
            else:
                running_info_parts.append("• 昨天没跑")

            if month_result and month_result[0] > 0:
                running_info_parts.append(f"• 本月跑了 {month_result[1]} 公里")
            else:
                running_info_parts.append("• 本月没跑")

            if year_result and year_result[0] > 0:
                running_info_parts.append(f"• 今年跑了 {year_result[1]} 公里")
            else:
                running_info_parts.append("• 今年没跑")

            return "Run：\n\n" + "\n".join(running_info_parts)

    except Exception as e:
        print(f"Error getting running data: {e}")
        return ""

    return ""


def get_day_of_year():
    now = pendulum.now(TIMEZONE)
    return now.day_of_year


def get_year_progress():
    """获取今年的进度条"""
    now = pendulum.now(TIMEZONE)
    day_of_year = now.day_of_year

    # 判断是否为闰年
    is_leap_year = now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0)
    total_days = 366 if is_leap_year else 365

    # 计算进度百分比
    progress_percent = (day_of_year / total_days) * 100

    # 生成进度条 (20个字符宽度)
    progress_bar_width = 20
    filled_blocks = int((day_of_year / total_days) * progress_bar_width)
    empty_blocks = progress_bar_width - filled_blocks

    progress_bar = "█" * filled_blocks + "░" * empty_blocks

    return f"{progress_bar} {progress_percent:.1f}% ({day_of_year}/{total_days})"


def get_today_get_up_status(issue):
    comments = list(issue.get_comments())
    if not comments:
        return False, []
    latest_comment = comments[-1]
    now = pendulum.now(TIMEZONE)
    latest_day = pendulum.instance(latest_comment.created_at).in_timezone(
        "Asia/Shanghai"
    )
    is_today = (latest_day.day == now.day) and (latest_day.month == now.month)
    return is_today


def make_get_up_message(github_token):
    sentence = get_one_sentence()
    now = pendulum.now(TIMEZONE)
    # 3 - 7 means early for me
    ###  make it to 9 in 2024.10.15 for maybe I forgot it ###
    is_get_up_early = 3 <= now.hour <= 9
    try:
        sentence = get_one_sentence()
        print(f"Poem: {sentence}")
    except Exception as e:
        print(str(e))

    day_of_year = get_day_of_year()
    year_progress = get_year_progress()
    github_activity = get_yesterday_github_activity(github_token)
    running_info = get_running_distance()
    history_today = get_history_today()
    street_view = get_random_street_view()

    return (
        sentence,
        is_get_up_early,
        day_of_year,
        year_progress,
        github_activity,
        running_info,
        history_today,
        street_view,
    )


def remove_github_links(text):
    # 移除所有 GitHub 链接，保留链接文本
    pattern = r"\[([^\]]+)\]\(https://github\.com/[^\)]+\)"
    cleaned_text = re.sub(pattern, r"\1", text)
    return cleaned_text


def main(
    github_token,
    repo_name,
    tele_token,
    tele_chat_id,
    dingtalk_webhook,
    dingtalk_secret,
):
    u = login(github_token)
    repo = u.get_repo(repo_name)
    try:
        # find the latest open issue with title "GET UP"
        issues = repo.get_issues(state="open")
        issue = None
        for i in issues:
            if i.title == "GET UP":
                issue = i
                break
        
        if not issue:
            # if not found, create it
            issue = repo.create_issue(title="GET UP", body="GET UP")
    except Exception as e:
        print(f"Error getting issue: {e}")
        # fallback: try to create a new issue if searching failed
        try:
            issue = repo.create_issue(title="GET UP", body="GET UP")
        except Exception as e2:
            print(f"Error creating issue: {e2}")
            return
        
    is_today = get_today_get_up_status(issue)
    if is_today:
        print("Today I have recorded the wake up time")
        return

    (
        sentence,
        is_get_up_early,
        day_of_year,
        year_progress,
        github_activity,
        running_info,
        history_today,
        street_view,
    ) = make_get_up_message(github_token)
    get_up_time = pendulum.now(TIMEZONE).to_datetime_string()

    body = GET_UP_MESSAGE_TEMPLATE.format(
        get_up_time=get_up_time,
        sentence=sentence,
        day_of_year=day_of_year,
        year_progress=year_progress,
        github_activity=github_activity,
        running_info=running_info,
        history_today=history_today,
        street_view=street_view,
    )


    if is_get_up_early:
        if tele_token and tele_chat_id:
            bot = telebot.TeleBot(tele_token)
            try:
                formatted_body = markdownify(body)
                bot.send_message(
                    tele_chat_id,
                    formatted_body,
                    parse_mode="MarkdownV2",
                    disable_notification=True,
                )
            except Exception as e:
                print(str(e))

        if dingtalk_webhook:
            print(f"Sending DingTalk message... Secret length: {len(dingtalk_secret) if dingtalk_secret else 0}")
            try:
                send_dingtalk_message(dingtalk_webhook, dingtalk_secret, body)
            except Exception as e:
                print(f"DingTalk exception: {str(e)}")
        else:
            print("No DingTalk webhook configured")

        cleaned_body = remove_github_links(body)
        issue.create_comment(cleaned_body)
    else:
        print("You wake up late")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("github_token", help="github_token")
    parser.add_argument("repo_name", help="repo_name")
    parser.add_argument(
        "--weather_message", help="weather_message", nargs="?", default="", const=""
    )
    parser.add_argument(
        "--tele_token", help="tele_token", nargs="?", default="", const=""
    )
    parser.add_argument(
        "--tele_chat_id", help="tele_chat_id", nargs="?", default="", const=""
    )
    parser.add_argument(
        "--dingtalk_webhook", help="dingtalk_webhook", nargs="?", default="", const=""
    )
    parser.add_argument(
        "--dingtalk_secret", help="dingtalk_secret", nargs="?", default="", const=""
    )
    options = parser.parse_args()
    main(
        options.github_token,
        options.repo_name,
        options.tele_token,
        options.tele_chat_id,
        options.dingtalk_webhook,
        options.dingtalk_secret,
    )
