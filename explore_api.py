"""探索 SEU 云课堂 API——寻找课程搜索端点"""
import requests, json, os, sys

cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seu_cookies.json")
with open(cookie_path) as f:
    cookies = json.load(f)

s = requests.Session()
s.cookies.update(cookies)
s.trust_env = False

h = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
}

base = "https://cvs.seu.edu.cn/jy-application-resourcemanage"

def try_api(method, path, **kwargs):
    """尝试一个 API 端点并报告结果"""
    url = f"{base}{path}"
    try:
        if method == "GET":
            r = s.get(url, headers=h, timeout=10, **kwargs)
        else:
            r = s.post(url, headers=h, timeout=10, **kwargs)

        size = len(r.content)
        if r.status_code == 200 and size > 100:
            try:
                data = r.json()
                # 尝试展示关键信息
                if isinstance(data, dict):
                    keys = list(data.keys())
                    data_block = data.get("data", {})
                    if isinstance(data_block, dict):
                        records = data_block.get("records") or data_block.get("list") or []
                        total = data_block.get("total") or data_block.get("rowCount") or "?"
                        if isinstance(records, list) and len(records) > 0:
                            rec = records[0]
                            name_fields = [k for k in rec.keys() if "name" in k.lower() or "title" in k.lower() or "subj" in k.lower()]
                            print(f"  HTTP 200 | {len(records)} records | keys: {list(rec.keys())[:8]}")
                            if name_fields:
                                print(f"    name fields: {name_fields}")
                                for r2 in records[:3]:
                                    vals = {k: r2.get(k) for k in name_fields}
                                    print(f"    {vals}")
                            return True
                    print(f"  HTTP 200 | keys: {keys} | data type: {type(data_block).__name__}")
                elif isinstance(data, list):
                    print(f"  HTTP 200 | list[{len(data)}]")
                    if len(data) > 0 and isinstance(data[0], dict):
                        print(f"    sample keys: {list(data[0].keys())[:8]}")
                return True
            except:
                print(f"  HTTP 200 | {size}b (not JSON)")
        elif r.status_code == 200:
            print(f"  HTTP 200 | {size}b (too small)")
        else:
            print(f"  HTTP {r.status_code} | {size}b")
    except Exception as e:
        print(f"  ERROR: {e}")
    return False

# ── 候选端点 ──
candidates = [
    # 课程/科目相关
    ("GET", "/v1/subject/list"),
    ("GET", "/v1/subject/search"),
    ("GET", "/v1/subject_vod_list"),
    ("GET", "/v1/subject_vod_list?teclIds=149551&page.pageIndex=1&page.pageSize=1"),
    ("GET", "/v1/group_subject_vod_list"),
    ("GET", "/v1/group_subject_vod_list/t-1"),
    ("GET", "/v1/group_subject_vod_list/t-1?teclId=149551"),
    # 搜索
    ("GET", "/v1/search"),
    ("GET", "/v1/search/course"),
    ("GET", "/v1/search/subject"),
    ("POST", "/v1/search", {"json": {"keyword": "机器人"}}),
    ("POST", "/v1/search/course", {"json": {"keyword": "机器人"}}),
    # 列表
    ("GET", "/v1/list/termYear"),
    ("GET", "/v1/list/subject"),
    ("GET", "/v1/list/course"),
    ("GET", "/v1/list/tecl"),  # 教学班列表
    ("GET", "/v1/tecl/list"),
    ("GET", "/v1/tecl/search"),
    # 用户相关（可能含已选课程）
    ("GET", "/v1/user/course"),
    ("GET", "/v1/user/subject"),
    ("GET", "/v1/user/tecl"),
    ("GET", "/v1/my/course"),
    ("GET", "/v1/my/subject"),
    ("GET", "/v1/personal/course"),
    # 学期
    ("GET", "/v1/term/list"),
    ("GET", "/v1/semester/list"),
    # 其他可能
    ("GET", "/v1/course/list"),
    ("GET", "/v1/course/search"),
    ("GET", "/v1/app/list"),
    ("GET", "/v1/app/info"),
]

print("=== 探索 SEU API 端点 ===\n")

hits = 0
for method, path, *extra in candidates:
    print(f"{method} {path}", end=" ... ")
    kwargs = extra[0] if extra else {}
    if try_api(method, path, **kwargs):
        hits += 1

print(f"\n命中: {hits}/{len(candidates)}")

# ── 也试试从 JS bundle 找路径 ──
print("\n=== 尝试下载 JS bundle 搜路径 ===")
try:
    r = s.get("https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/", headers=h, timeout=10)
    html = r.text
    # 找 JS 文件名
    import re
    js_files = re.findall(r'src="(\./static/js/[^"]+\.js)"', html)
    print(f"找到 {len(js_files)} 个 JS 文件")
    for js in js_files[:3]:
        js_url = f"https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/{js[2:]}"
        try:
            r2 = s.get(js_url, headers=h, timeout=10)
            print(f"  {js}: HTTP {r2.status_code}, {len(r2.text)} bytes")
            if r2.status_code == 200:
                # 搜 /v1/ 路径
                paths = set(re.findall(r'"(/v1/[a-zA-Z0-9_/]+)"', r2.text))
                if paths:
                    print(f"    找到 {len(paths)} 个 API 路径:")
                    for p in sorted(paths)[:20]:
                        print(f"      {p}")
        except:
            pass
except Exception as e:
    print(f"  ERROR: {e}")
