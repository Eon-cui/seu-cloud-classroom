"""CDP 自动提取 SEU 云课堂 Cookie（跨平台 / 不动你正在用的浏览器）

为什么不"杀掉浏览器再开"：
  Chromium 136+（Edge 136+ / Chrome 136+）对 **默认 profile** 禁用了
  --remote-debugging-port，杀进程重开也拿不到 CDP 端口。
  所以这里改用**独立 profile** 另开一个窗口：登录态持久保存在该 profile 里，
  下次直接复用，完全不影响用户平时的浏览器窗口。

用法:
  python get_all_cookies.py                  # 推荐：另开独立 profile 窗口，等登录，自动取 cookie
  python get_all_cookies.py --attach         # 已有带 CDP 的浏览器在跑 -> 直接取，不再开窗口
  python get_all_cookies.py --port 9222      # 自定义调试端口
  python get_all_cookies.py --profile DIR    # 自定义 profile 目录（登录态留在哪）
  python get_all_cookies.py --browser chrome # 指定浏览器；默认自动找 Edge -> Chrome
  python get_all_cookies.py --timeout 900    # 等待登录的秒数
  python get_all_cookies.py --force          # 旧行为：关闭所有 Edge/Chrome 后再连（拿不到 CDP 时才用）

退出码:
  0 - 成功
  1 - 没找到可用浏览器
  2 - 等待登录超时
  3 - CDP 端口起不来（profile 被占用等）
  8 - 取到 cookie 但数量不全
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

try:
    import websocket  # websocket-client
except ImportError:
    print("错误: 缺少依赖 websocket-client")
    print("请运行: pip install websocket-client")
    sys.exit(1)

NEEDED = [
    "007d0115-a0c0-4713-a023-75bc0ff16a59",
    "route",
    "jy-application-resourcemanage",
    "_bl_usercode",
    "_bl_dept",
]

SEU_URL = "https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seu_cookies.json")

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


def default_profile():
    """独立 profile 的默认位置（登录态留在这，下次复用）"""
    if IS_WIN:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif IS_MAC:
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "seu-cloud-classroom", "cdp-profile")


def find_browser(prefer=None):
    """返回 [(名称, 路径)]，按优先级排序"""
    cands = []
    if IS_WIN:
        cands = [
            ("Edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            ("Edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            ("Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            ("Chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        ]
        for name in ("msedge", "chrome"):
            found = shutil.which(name)
            if found:
                cands.append((name.title(), found))
    elif IS_MAC:
        cands = [
            ("Edge", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            ("Chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:
        for cmd, label in (
            ("microsoft-edge", "Edge"),
            ("google-chrome", "Chrome"),
            ("chromium", "Chromium"),
            ("chromium-browser", "Chromium"),
        ):
            found = shutil.which(cmd)
            if found:
                cands.append((label, found))

    out = [(n, p) for n, p in cands if p and os.path.exists(p)]
    if prefer:
        out.sort(key=lambda x: 0 if x[0].lower().startswith(prefer.lower()) else 1)
    return out


def kill_browsers():
    print("关闭现有 Edge/Chrome 进程（--force）...")
    if IS_WIN:
        for proc in ("msedge", "chrome"):
            subprocess.run(["taskkill", "/F", "/IM", f"{proc}.exe"], capture_output=True)
    else:
        for proc in ("Microsoft Edge", "Google Chrome", "chrome", "chromium"):
            subprocess.run(["pkill", "-f", proc], capture_output=True)
    time.sleep(3)


def cdp_get(port, path, timeout=5):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def cdp_alive(port):
    try:
        cdp_get(port, "/json/version", timeout=3)
        return True
    except Exception:
        return False


def find_seu_page(port):
    try:
        pages = cdp_get(port, "/json")
    except Exception:
        return None
    for p in pages:
        url = p.get("url", "")
        if "cvs.seu.edu.cn" in url and "auth" not in url.lower():
            return p
    for p in pages:
        url = p.get("url", "")
        if "cvs.seu.edu.cn" in url or "auth.seu.edu.cn" in url:
            return p
    return None


def extract_cookies(port, ws_url):
    ws = websocket.create_connection(ws_url, timeout=15)
    try:
        ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
        resp = json.loads(ws.recv())
    finally:
        ws.close()
    found = {}
    for c in resp.get("result", {}).get("cookies", []):
        if c.get("name") in NEEDED:
            found[c["name"]] = c["value"]
    return found


def validate(found):
    """打 /authority/me 验证 cookie 真能用；网络不通时只警告"""
    try:
        import requests
    except ImportError:
        return None, "未安装 requests，跳过校验"
    s = requests.Session()
    s.cookies.update(found)
    s.trust_env = False
    try:
        r = s.get(
            "https://cvs.seu.edu.cn/jy-application-resourcemanage/authority/me",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": SEU_URL,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
            timeout=20,
        )
        return r.status_code, r.text[:160]
    except Exception as e:
        return None, f"校验请求失败（VPN 未连？）: {e}"


def save(found):
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(found, f, indent=2)
    print(f"已保存 {len(found)} 个 cookie -> {COOKIE_FILE}")


def finish(found, quiet_validate):
    save(found)
    if not quiet_validate:
        code, body = validate(found)
        if code == 200:
            print(f"校验通过（HTTP 200）: {body[:80]}")
        else:
            print(f"注意：校验没通过（{code}）{body}")
            print("      cookie 已存，但可能还没登录成功，或 VPN 没连。")


def main():
    ap = argparse.ArgumentParser(
        description="通过 CDP 提取 SEU 云课堂 cookie（独立 profile，不杀你正在用的浏览器）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--attach", action="store_true", help="已有带 CDP 的浏览器在跑时直接取，不开新窗口")
    ap.add_argument("--port", type=int, default=9222, help="调试端口，默认 9222")
    ap.add_argument("--profile", default=None, help="profile 目录（默认 LOCALAPPDATA/seu-cloud-classroom/cdp-profile）")
    ap.add_argument("--browser", default=None, help="edge / chrome，默认自动")
    ap.add_argument("--timeout", type=int, default=600, help="等待登录秒数，默认 600")
    ap.add_argument("--force", action="store_true", help="先关闭所有 Edge/Chrome（旧行为）")
    ap.add_argument("--quiet-validate", action="store_true", help="不校验 cookie（省一次请求）")
    args = ap.parse_args()
    port = args.port

    if cdp_alive(port):
        print(f"CDP 端口 {port} 已就绪，直接取 cookie...")
        page = find_seu_page(port)
        if page:
            found = extract_cookies(port, page["webSocketDebuggerUrl"])
            if len(found) == len(NEEDED):
                finish(found, args.quiet_validate)
                return 0
            print(f"缺 {len(NEEDED) - len(found)} 个 cookie，可能需要先登录。")
        else:
            print("CDP 在，但没找到 cvs.seu.edu.cn 页面。")
        if args.attach:
            return 8
    elif args.attach:
        print(f"CDP 端口 {port} 没有在监听。先开一个带 --remote-debugging-port={port} 的浏览器，再带 --attach 复用。")
        return 3

    browsers = find_browser(args.browser)
    if not browsers:
        print("错误: 没找到 Edge 或 Chrome，请先装一个。")
        return 1
    name, path = browsers[0]
    print(f"使用浏览器: {name} ({path})")

    if args.force:
        kill_browsers()

    profile = args.profile or default_profile()
    print(f"独立 profile: {profile}")
    print("会另开一个浏览器窗口（不影响你在用的窗口），请在里头完成 SEU CAS 登录。")

    proc = None
    for prof in [profile] + [f"{profile}-{i}" for i in range(2, 5)]:
        os.makedirs(prof, exist_ok=True)
        proc = subprocess.Popen(
            [
                path,
                f"--remote-debugging-port={port}",
                "--remote-allow-origins=*",
                f"--user-data-dir={prof}",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                SEU_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(5)
        if proc.poll() is None and cdp_alive(port):
            print(f"窗口已就绪（profile: {os.path.basename(prof)}）")
            break
        if proc.poll() is not None:
            print(f"profile {os.path.basename(prof)} 被已有实例接管，换下一个...")
            proc = None
    if proc is None:
        print("错误: 起不来带调试端口的窗口（profile 被占用？）")
        print("     关掉残留窗口后重试，或 python get_all_cookies.py --force")
        return 3

    deadline = time.time() + args.timeout
    last_missing = None
    print("等待登录", end="", flush=True)
    while time.time() < deadline:
        time.sleep(3)
        print(".", end="", flush=True)
        if proc.poll() is not None:
            print(f"\n浏览器已退出（code={proc.returncode}）")
            return 3
        page = find_seu_page(port)
        if not page:
            continue
        try:
            found = extract_cookies(port, page["webSocketDebuggerUrl"])
        except Exception:
            continue
        if len(found) == len(NEEDED):
            print()
            finish(found, args.quiet_validate)
            print("窗口可以关掉了；登录态留在该 profile 里，下次不用再登。")
            return 0
        missing = [n for n in NEEDED if n not in found]
        if missing != last_missing:
            print(f"\n  还缺: {missing}", end="", flush=True)
            last_missing = missing

    print(f"\n超时（{args.timeout}s）：没等到完整登录。")
    return 2


if __name__ == "__main__":
    sys.exit(main())
