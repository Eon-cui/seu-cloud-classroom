"""SEU 云课堂字幕爬虫——生产版

用法: python scrape.py <teclId> <课程名> [教师名]
示例: python scrape.py 149551 统一机器人学1 司伟

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

检测流程:
  ① VPN 连通性 → ② Cookie 有效性 → ③ teclId → ④ 逐节下载
  每步失败都打印具体原因和修复建议。
"""
import requests, json, os, sys, ctypes, time


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
# 检测点 ①：VPN 连通性
# ═══════════════════════════════════════════════════════════

def check_vpn():
    """检测是否能到达 SEU 服务器"""
    print("① 检测 VPN 连通性...", end=" ")
    try:
        r = requests.get("https://cvs.seu.edu.cn", timeout=10)
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
    except Exception as e:
        print(red(f"异常: {e}"))

    print(yellow("\n  请检查:"))
    print("    1. 是否已连接 SEU VPN (aTrust)?")
    print("    2. VPN 是否已登录并显示「已连接」?")
    print("    3. 可以浏览器打开 https://cvs.seu.edu.cn 验证")
    print()
    return False


# ═══════════════════════════════════════════════════════════
# 检测点 ②：Cookie 有效性
# ═══════════════════════════════════════════════════════════

def check_cookie(session, headers, base):
    """检测 cookie 是否有效"""
    print("② 检测 Cookie 有效性...", end=" ")
    try:
        r = session.get(f"{base}/authority/me", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == "0":
                print(green("OK"))
                return True
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


# ═══════════════════════════════════════════════════════════
# 检测点 ③：teclId 有效性
# ═══════════════════════════════════════════════════════════

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
        }, timeout=30)

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


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    # ── 参数 ──
    if len(sys.argv) < 3:
        print("用法: python scrape.py <teclId> <课程名> [教师名]")
        print("示例: python scrape.py 149551 统一机器人学1 司伟")
        sys.exit(1)

    teclId = sys.argv[1]
    course_name = sys.argv[2]
    teacher = sys.argv[3] if len(sys.argv) > 3 else ""

    print(f"目标: {course_name} ({teacher or '未知教师'}) | teclId={teclId}")
    print("=" * 50)

    # ── 检测 ①：VPN ──
    if not check_vpn():
        sys.exit(2)

    # ── 加载 cookie ──
    cookie_path = os.path.join(os.path.dirname(__file__), "seu_cookies.json")
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

    base = "https://cvs.seu.edu.cn/jy-application-resourcemanage"

    # ── 检测 ②：Cookie ──
    if not check_cookie(s, headers, base):
        sys.exit(3)

    # ── 检测 ③：课程列表 ──
    records = fetch_course_list(s, headers, base, teclId)
    if not records:
        sys.exit(4)

    # ── 课程信息 ──
    subj_name = records[0].get("subjName", course_name)
    teachers = records[0].get("teclTeacNames", [teacher])
    print(f"\n课程: {subj_name}")
    print(f"教师: {', '.join(teachers) if teachers else '未知'}")
    print(f"节数: {len(records)}")
    first = (records[0].get("courBeginTime") or "")[:10]
    last = (records[-1].get("courBeginTime") or "")[:10]
    print(f"时间: {first} ~ {last}")

    # ── 输出目录 ──
    WEEK_DAY = ["一", "二", "三", "四", "五", "六", "日"]
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
        week_day_num = rec.get("week", 0)
        week_day_name = WEEK_DAY[week_day_num - 1] if 1 <= week_day_num <= 7 else str(week_day_num)
        date = (rec.get("courBeginTime") or "")[:10]

        # 子目录：第X周_周X_第X节
        lesson_dir_name = f"第{week_no}周_周{week_day_name}_第{leti}节"
        lesson_dir = os.path.join(output_dir, lesson_dir_name)
        os.makedirs(lesson_dir, exist_ok=True)

        try:
            r = s.get(f"{base}/v1/course_vod_subtitle", headers=headers,
                       params={"courseId": rid}, timeout=30)

            if r.status_code == 200 and len(r.content) > 100:
                items = r.json().get("data", [])
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
