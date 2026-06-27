"""CDP 自动提取 SEU 云课堂 Cookie（跨平台）

支持: Edge / Chrome / Chromium 系浏览器
平台: Windows / macOS / Linux

前提: 用户已在浏览器登录 cvs.seu.edu.cn（或脚本会打开浏览器等用户登录）
输出: ./seu_cookies.json（脚本同级目录）
"""
import urllib.request, urllib.error, json, sys, os, platform, subprocess, time, shutil

# 提前检查 websocket-client 依赖，避免用户登录后才发现没装
try:
    import websocket
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

CDP_PORT = 9222
CDP_BASE = f"http://localhost:{CDP_PORT}"
SEU_URL = "https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/"


# ── 平台检测 ──
SYSTEM = platform.system()
IS_WIN = SYSTEM == "Windows"
IS_MAC = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"


# ── 查找浏览器 ──
def find_browser():
    """依次查找可用的 Chromium 浏览器，返回 (名称, 路径)"""
    candidates = []

    if IS_WIN:
        candidates = [
            ("Edge", "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"),
            ("Edge", "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"),
            ("Chrome", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
            ("Chrome", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"),
        ]
        # 也搜 PATH
        for name in ["msedge", "chrome"]:
            found = shutil.which(name)
            if found:
                candidates.append((name.title(), found))
    elif IS_MAC:
        candidates = [
            ("Edge", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            ("Chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif IS_LINUX:
        for name in ["microsoft-edge", "google-chrome", "chromium", "chromium-browser"]:
            found = shutil.which(name)
            if found:
                browser_name = {"microsoft-edge": "Edge", "google-chrome": "Chrome", "chromium": "Chromium", "chromium-browser": "Chromium"}.get(name, name)
                candidates.append((browser_name, found))

    for browser_name, path in candidates:
        if path and os.path.exists(path):
            return browser_name, path

    return None, None


# ── 检查 CDP 是否已运行 ──
def cdp_available():
    try:
        urllib.request.urlopen(f"{CDP_BASE}/json/version", timeout=2)
        return True
    except Exception:
        return False


# ── 找到 SEU 页面 ──
def find_seu_page():
    try:
        r = urllib.request.urlopen(f"{CDP_BASE}/json", timeout=5)
        pages = json.loads(r.read())
    except Exception as e:
        print(f"无法连接 CDP: {e}")
        return None

    for p in pages:
        url = p.get("url", "")
        if "cvs.seu.edu.cn" in url and "auth" not in url.lower():
            return p

    # 没找到已登录的 SEU 页面，返回任意 SEU 页面（可能在 CAS 登录页）
    for p in pages:
        url = p.get("url", "")
        if "cvs.seu.edu.cn" in url or "auth.seu.edu.cn" in url:
            return p

    return None


# ── 提取 cookie ──
def extract_cookies(ws_url):
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
    resp = json.loads(ws.recv())
    ws.close()

    all_cookies = resp.get("result", {}).get("cookies", [])
    found = {}
    for c in all_cookies:
        if c["name"] in NEEDED:
            found[c["name"]] = c["value"]
    return found


# ── 主流程 ──
def main():
    # 1. 检查 CDP 是否已开
    if cdp_available():
        print("CDP 端口已开，直接提取...")
        page = find_seu_page()
        if page:
            found = extract_cookies(page["webSocketDebuggerUrl"])
            if len(found) == len(NEEDED):
                save(found)
                return
            else:
                missing = [n for n in NEEDED if n not in found]
                print(f"缺少 {len(missing)} 个 cookie: {missing}")
                print("可能需要重新登录...")
        else:
            print("CDP 已开但没找到 SEU 页面")

    # 2. 查找浏览器
    browser_name, browser_path = find_browser()
    if not browser_name:
        print("错误: 没找到 Edge 或 Chrome 浏览器")
        print("请手动安装 Chromium 系浏览器")
        sys.exit(1)

    print(f"使用浏览器: {browser_name} ({browser_path})")

    # 3. 关掉旧实例（需 --force 确认）
    if "--force" not in sys.argv:
        print("⚠ 脚本将关闭所有 Edge/Chrome 浏览器窗口。")
        print("  如有未保存工作，请先保存。")
        print(f"  确认后重新运行: python get_all_cookies.py --force")
        sys.exit(7)

    print("关闭现有浏览器进程...")
    if IS_WIN:
        for proc in ["msedge", "chrome"]:
            subprocess.run(["taskkill", "/F", "/IM", f"{proc}.exe"], capture_output=True)
    else:
        for proc in ["Microsoft Edge", "Google Chrome"]:
            subprocess.run(["pkill", "-f", proc], capture_output=True)

    time.sleep(3)  # 等浏览器完全释放锁

    print(f"启动 {browser_name}（debug 端口 {CDP_PORT}）...")

    # 先开 SEU 页面，再开新标签到 SEU（确保有窗口可连）
    subprocess.Popen([
        browser_path,
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        SEU_URL,
    ], start_new_session=True)

    # 4. 等待 CDP 就绪 + 用户登录
    print(f"\n浏览器已打开，请完成 CAS 登录...")
    print("等待 cookie 出现", end="", flush=True)

    max_wait = 120
    for i in range(max_wait):
        time.sleep(2)
        print(".", end="", flush=True)

        try:
            page = find_seu_page()
            if not page:
                continue

            found = extract_cookies(page["webSocketDebuggerUrl"])
            if len(found) == len(NEEDED):
                print("\n")
                save(found)
                return
        except Exception:
            continue

    print(f"\n超时（{max_wait*2}秒）。请检查是否已登录。")
    sys.exit(2)


def save(found):
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seu_cookies.json")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(found, f, indent=2)
    print(f"已保存 {len(found)} 个 cookie → {save_path}")


if __name__ == "__main__":
    main()
