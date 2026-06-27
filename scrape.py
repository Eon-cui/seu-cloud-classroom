"""SEU 云课堂字幕爬虫——生产版

用法:
  python scrape.py --search <关键词>                       # 搜索课程，返回 teclId
  python scrape.py <teclId> <课程名> [教师名] [--weeks 范围]
  python scrape.py <teclId> <课程名> [教师名] --dry-run

示例:
  python scrape.py --search 统一机器人                      # 搜课程
  python scrape.py 149551 统一机器人学1 司伟 --weeks 1-5    # 第1~5周

输出结构:
  ~/Desktop/统一机器人学1_司伟_字幕爬取/
    ├── 第14周_周四_第8节/
    │   └── 2026-06-04_字幕.txt
    └── ...

退出码:
  0 - 全部完成
  1 - 参数缺失
  2 - VPN 未连接 / 网络不通
  3 - Cookie 过期或无效
  4 - teclId 不存在或课程为空
  5 - 部分字幕下载失败（已完成部分已保存）
  6 - 未指定 --weeks（打印周次分布后退出，由 AI 询问用户）

检测流程:
  ① VPN → ② Cookie → ③ 课程列表 → ④ 显示周次 → ⑤ 用户确认范围 → ⑥ 下载
"""
import requests, json, os, sys, ctypes
from collections import Counter

WEEK_DAY = ["一", "二", "三", "四", "五", "六", "日"]
API_BASE = "https://cvs.seu.edu.cn/jy-application-resourcemanage"
TIMEOUT_SHORT = 10
TIMEOUT_LONG = 30


def get_desktop():
    """获取真实桌面路径（处理 Windows 桌面重定向 / OneDrive）"""
    if os.name == "nt":
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)
        return buf.value
    return os.path.expanduser("~/Desktop")


def red(text):
    """终端红色"""
    return f"\033[91m{text}\033[0m"


def green(text):
    return f"\033[92m{text}\033[0m"


def yellow(text):
    return f"\033[93m{text}\033[0m"


def parse_weeks(arg):
    """解析 --weeks 参数，返回 set of int。
    格式: "1-5" / "3" / "1-3,7,9-12"
    """
    weeks = set()
    for part in arg.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                a_str, b_str = part.split("-", 1)
                a, b = int(a_str), int(b_str)
                if a > b:
                    a, b = b, a
                weeks.update(range(a, b + 1))
            else:
                weeks.add(int(part))
        except ValueError:
            print(red(f"无效周次: '{part}'"))
            print("格式: --weeks 1-5 或 --weeks 3,7,10")
            sys.exit(1)
    return weeks


def show_week_summary(records):
    """打印周次分布，返回 (min_week, max_week)"""
    week_counts = Counter()
    for rec in records:
        wn = rec.get("weekNo")
        if wn is not None:
            week_counts[wn] += 1

    if not week_counts:
        return None, None

    sorted_weeks = sorted(week_counts.keys())
    print(f"\n周次分布（共 {len(sorted_weeks)} 周）:")
    print(f"  第{sorted_weeks[0]}周 ~ 第{sorted_weeks[-1]}周")

    # 压缩显示：连续周用范围，不连续用逗号
    ranges = []
    start = sorted_weeks[0]
    end = start
    for w in sorted_weeks[1:]:
        if w == end + 1:
            end = w
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = w
    ranges.append(f"{start}-{end}" if start != end else str(start))
    print(f"  范围: {', '.join(ranges)}")
    print(f"  节数: {sum(week_counts.values())}")

    # 每周明细
    print("  明细:")
    for w in sorted_weeks:
        count = week_counts[w]
        # 找这周的第一天和最后一天
        dates = sorted((r.get("courBeginTime") or "")[:10] for r in records if r.get("weekNo") == w)
        bar = "█" * min(count, 20)
        date_range = f"{dates[0]}~{dates[-1]}" if len(dates) > 1 else (dates[0] if dates else "?")
        print(f"    第{w:2d}周 {bar} {count}节  {date_range}")

    return sorted_weeks[0], sorted_weeks[-1]


def search_courses(keyword, session, headers):
    """按课程名搜索全部教学班，翻页拿全量。
    用 group_subject_vod_list——能返回所有班级，不受当前用户选课限制。
    返回 [(teclId, subjName, subjCode, teachers, orgaNames)]
    """
    print(f"搜索课程「{keyword}」...", end=" ", flush=True)
    try:
        seen = set()
        results = []
        for page in range(1, 20):
            r = session.get(f"{API_BASE}/v1/group_subject_vod_list", headers=headers, params={
                "subjName": keyword,
                "page.pageIndex": page,
                "page.pageSize": 50,
            }, timeout=TIMEOUT_SHORT)
            data = r.json()
            records = data.get("data", {}).get("records", [])
            if not records:
                break
            for rec in records:
                teclId = rec.get("teclId")
                name = rec.get("subjName", "?")
                if (teclId, name) in seen:
                    continue
                seen.add((teclId, name))
                results.append((
                    teclId,
                    name,
                    rec.get("subjCode", "?"),
                    rec.get("teacNames", []),
                    rec.get("orgaNames", []),
                ))
            if len(records) < 50:
                break
        print(green(f"{len(results)} 条"))
        return results
    except Exception as e:
        print(red(f"搜索失败: {e}"))
        return []


def check_vpn():
    """检测是否能到达 SEU 服务器"""
    print("① 检测 VPN 连通性...", end=" ")
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get("https://cvs.seu.edu.cn", timeout=TIMEOUT_SHORT)
        # 403 也说明连通（无 cookie 被拒）
        if r.status_code in (200, 403, 302):
            print(green("OK"))
            return True
    except requests.exceptions.ConnectTimeout:
        print(red("超时"))
        print(red("  → 无法连接 cvs.seu.edu.cn"))
    except requests.exceptions.ConnectionError:
        print(red("连接失败"))
        print(red("  → 无法连接 cvs.seu.edu.cn"))
    except requests.exceptions.SSLError:
        print(red("SSL 错误"))
        print(red("  → VPN 可能在做证书劫持，检查 VPN 配置"))
    except Exception as e:
        print(red(f"异常: {e}"))

    print(yellow("\n  请检查:"))
    print("    1. 是否已连接 SEU VPN (aTrust)?")
    print("    2. VPN 是否已登录并显示「已连接」?")
    print("    3. 可以浏览器打开 https://cvs.seu.edu.cn 验证")
    print()
    return False


def check_cookie(session, headers, base):
    """检测 cookie 是否有效"""
    print("② 检测 Cookie 有效性...", end=" ")
    try:
        r = session.get(f"{base}/authority/me", headers=headers, timeout=TIMEOUT_SHORT)
        if r.status_code == 200:
            data = r.json()
            code = data.get("code")
            if code == "0":
                print(green("OK"))
                return True
            # HTTP 200 但业务码非 0
            msg = data.get("message") or data.get("msg", "")
            print(red(f"业务错误 (code={code})"))
            print(red(f"  → {msg}"))
        else:
            print(red(f"HTTP {r.status_code}"))
            if r.status_code == 401:
                print(red("  → Cookie 已过期（401 Unauthorized）"))
            elif r.status_code == 500:
                print(red("  → Cookie 无效（500 服务器拒绝）"))
            else:
                print(red(f"  → 异常状态码 {r.status_code}"))
    except Exception as e:
        print(red(f"异常: {e}"))

    print(yellow("\n  请重新提取 Cookie:"))
    print("    python get_all_cookies.py")
    print()
    return False


def fetch_course_list(session, headers, base, teclId):
    """获取课程列表，返回 records 或 None"""
    print(f"③ 获取课程列表 (teclId={teclId})...", end=" ")
    try:
        r = session.get(f"{base}/v1/subject_vod_list_new", headers=headers, params={
            "teclIds": teclId,
            "page.pageIndex": 1,
            "page.pageSize": 200,
            "page.orders[0].asc": "false",
            "page.orders[0].field": "courBeginTime",
            "schoolOpenStatusFlag": "false",
        }, timeout=TIMEOUT_LONG)

        if r.status_code != 200:
            print(red(f"HTTP {r.status_code}"))
            print(red(f"  响应: {r.text[:200]}"))
            return None

        data = r.json()
        records = data.get("data", {}).get("records", [])
        if not records:
            print(red("课程列表为空"))
            data_block = data.get("data", {})
            total = data_block.get("total") or data_block.get("rowCount", 0)
            if total == 0:
                print(red(f"  → teclId={teclId} 下没有课程记录"))
                print(yellow("\n  请检查 teclId 是否正确:"))
                print("    1. 在浏览器打开课程播放页")
                print("    2. 从 URL 提取 teclId 参数")
                print("    3. 例如: https://cvs.seu.edu.cn/.../#/play-center?teclId=149551&...")
            else:
                print(red(f"  → total={total} 但 records 为空（可能是分页问题）"))
            return None

        print(green(f"OK ({len(records)} 节)"))
        return records

    except requests.exceptions.Timeout:
        print(red("超时"))
        print(red("  → 请求超时，检查 VPN 是否稳定"))
        return None
    except Exception as e:
        print(red(f"异常: {e}"))
        return None


def main():
    # ── 参数 ──
    positional = []
    week_filter = None
    dry_run = False
    search_term = None

    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--dry-run":
            dry_run = True
        elif a == "--search":
            i += 1
            if i < len(sys.argv):
                search_term = sys.argv[i]
        elif a.startswith("--search="):
            search_term = a.split("=", 1)[1]
        elif a == "--weeks":
            i += 1
            if i < len(sys.argv):
                week_filter = parse_weeks(sys.argv[i])
        elif a.startswith("--weeks="):
            week_filter = parse_weeks(a.split("=", 1)[1])
        elif not a.startswith("--"):
            positional.append(a)
        i += 1

    # ── --search 模式：搜索课程 → 打印结果 → 退出 ──
    if search_term:
        if not check_vpn():
            sys.exit(2)
        cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seu_cookies.json")
        if not os.path.exists(cookie_path):
            print(red(f"未找到 Cookie: {cookie_path}"))
            sys.exit(3)
        with open(cookie_path) as f:
            cookies = json.load(f)
        s = requests.Session()
        s.cookies.update(cookies)
        s.trust_env = False
        results = search_courses(search_term, s, {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        })
        if results:
            print(f"\n{'课程名':28s} {'编号':10s} {'teclId':8s} {'教师'}")
            print("-" * 90)
            for teclId, name, code, teachers, org in results:
                print(f"{name:28s} {code:10s} {str(teclId):8s} {', '.join(teachers)}")
            print(f"\n共 {len(results)} 个教学班。下载时须指定 teclId。")
        else:
            print(yellow("未找到匹配课程"))
        sys.exit(0)

    if len(positional) < 2:
        print("用法:")
        print("  python scrape.py --search <关键词>                    # 搜索课程")
        print("  python scrape.py <teclId> <课程名> [教师名] [--weeks 范围]")
        print("  python scrape.py <teclId> <课程名> [教师名] --dry-run")
        sys.exit(1)

    teclId = positional[0]
    course_name = positional[1]
    teacher = positional[2] if len(positional) > 2 else ""

    print(f"目标: {course_name} ({teacher or '未知教师'}) | teclId={teclId}")
    if week_filter:
        print(f"周次: {sorted(week_filter)}")
    if dry_run:
        print("模式: 只查看（不下载）")
    print("=" * 50)

    # ── 检测 ①：VPN ──
    if not check_vpn():
        sys.exit(2)

    # ── 加载 cookie ──
    cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seu_cookies.json")
    if not os.path.exists(cookie_path):
        print(red(f"未找到 Cookie 文件: {cookie_path}"))
        print(yellow("请运行: python get_all_cookies.py"))
        sys.exit(3)

    with open(cookie_path) as f:
        cookies = json.load(f)

    # ── Session ──
    s = requests.Session()
    s.cookies.update(cookies)
    s.trust_env = False

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    }

    # ── 检测 ②：Cookie ──
    if not check_cookie(s, headers, API_BASE):
        sys.exit(3)

    # ── 检测 ③：课程列表 ──
    records = fetch_course_list(s, headers, API_BASE, teclId)
    if not records:
        sys.exit(4)

    # ── 课程信息 ──
    subj_name = records[0].get("subjName", course_name)
    teachers = records[0].get("teclTeacNames", [teacher])
    print(f"\n课程: {subj_name}")
    print(f"教师: {', '.join(teachers) if teachers else '未知'}")
    print(f"总节数: {len(records)}")
    first = (records[0].get("courBeginTime") or "")[:10]
    last = (records[-1].get("courBeginTime") or "")[:10]
    print(f"时间: {first} ~ {last}")

    # ── 周次分布 ──
    min_week, max_week = show_week_summary(records)

    # ── dry-run：只显示不下载 ──
    if dry_run:
        print(f"\n{'=' * 50}")
        print("--dry-run 模式，不下载。")
        print("请使用 --weeks 参数指定周次范围：")
        if min_week and max_week:
            print(f"  python scrape.py {teclId} \"{course_name}\" \"{teacher}\" --weeks {min_week}-{max_week}")
        sys.exit(0)

    # ── 没有指定 weeks → 提示后退出，让 AI 问用户 ──
    if week_filter is None:
        print(f"\n{'=' * 50}")
        print(yellow("未指定 --weeks。请指定要下载的周次范围："))
        if min_week and max_week:
            print(f"  python scrape.py {teclId} \"{course_name}\" \"{teacher}\" --weeks {min_week}-{max_week}  # 全部")
            print(f"  python scrape.py {teclId} \"{course_name}\" \"{teacher}\" --weeks 1-5       # 第1~5周")
        sys.exit(6)

    # ── 过滤 records ──
    filtered = [r for r in records if r.get("weekNo") in week_filter]
    if not filtered:
        print(red(f"\n周次 {sorted(week_filter)} 没有匹配的课程记录"))
        print(f"可用范围: 第{min_week}周 ~ 第{max_week}周")
        sys.exit(4)

    print(f"\n筛选: 第{min(week_filter)}周 ~ 第{max(week_filter)}周 → {len(filtered)} 节")
    records = filtered

    # ── 输出目录 ──
    label = f"{course_name}_{teacher}".rstrip("_")
    output_dir = os.path.join(get_desktop(), f"{label}_字幕爬取")
    os.makedirs(output_dir, exist_ok=True)
    print(f"输出: {output_dir}")

    # ── 逐节下载 ──
    print(f"\n{'=' * 50}")
    print("下载字幕...")

    ok = 0
    empty = 0
    failed = 0

    for i, rec in enumerate(records):
        rid = rec["id"]
        leti = rec.get("letiNumber", i + 1)
        week_no = rec.get("weekNo", "?")
        week_day_num = rec.get("week")
        if week_day_num is not None and 1 <= week_day_num <= 7:
            week_day_name = WEEK_DAY[week_day_num - 1]
        else:
            week_day_name = "?"  # 字段缺失不静默映射
        date = (rec.get("courBeginTime") or "")[:10]

        # 子目录：第X周_周X_第X节
        lesson_dir_name = f"第{week_no}周_周{week_day_name}_第{leti}节"
        lesson_dir = os.path.join(output_dir, lesson_dir_name)
        os.makedirs(lesson_dir, exist_ok=True)

        try:
            r = s.get(f"{API_BASE}/v1/course_vod_subtitle", headers=headers,
                       params={"courseId": rid}, timeout=TIMEOUT_LONG)

            if r.status_code == 200 and len(r.content) > 100:
                items = r.json().get("data") or []  # .get("data", []) 遇 null 返回 None
                texts = [it["res"].strip() for it in items if it.get("res", "").strip()]
                if texts:
                    fname = f"{date}_字幕.txt"
                    fpath = os.path.join(lesson_dir, fname)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(texts))
                    ok += 1
                    print(f"  [{i+1:02d}/{len(records)}] {green('OK')} {lesson_dir_name}/{fname} ({len(texts)} 行)")
                else:
                    empty += 1
                    print(f"  [{i+1:02d}/{len(records)}] {yellow('空')} {lesson_dir_name} 无字幕数据")
            else:
                failed += 1
                print(f"  [{i+1:02d}/{len(records)}] {red(f'HTTP {r.status_code}')} {lesson_dir_name}")
        except Exception as e:
            failed += 1
            print(f"  [{i+1:02d}/{len(records)}] {red(f'错误: {e}')} {lesson_dir_name}")

    # ── 结果摘要 ──
    print(f"\n{'=' * 50}")
    print(f"完成: {green(str(ok))} 有字幕, "
          f"{yellow(str(empty))} 空, "
          f"{red(str(failed))} 失败")
    print(f"目录: {output_dir}")

    if failed > 0 and ok == 0:
        print(red("\n全部失败！可能是网络波动或 API 限流，稍后重试。"))
        sys.exit(5)
    elif failed > 0:
        print(yellow(f"\n{failed} 节失败，可以重新运行脚本重试（已下载的会覆盖）。"))
        sys.exit(5)

    sys.exit(0)


if __name__ == "__main__":
    main()
