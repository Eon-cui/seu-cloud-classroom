# seu-cloud-classroom

东南大学云课堂 (cvs.seu.edu.cn) 字幕下载工具。

## 功能

- **课程搜索** — 输入关键词自动找到 teclId
- **周次过滤** — 只爬指定周，避免下载 84 节
- **一键字幕** — AI 语音识别文本，按周/节日历归档
- **自动 Cookie** — CDP 协议提取，无需 F12 手动复制
- **备考大纲** — 扫描字幕提取考试范围（可选）
- **跨平台** — Windows / macOS / Linux，Edge / Chrome 全支持

## 安装

```bash
git clone https://github.com/Eon-cui/seu-cloud-classroom.git
cd seu-cloud-classroom
pip install -r requirements.txt
```

## 使用

> **前提**: SEU VPN (aTrust) 已连接。

### 1. 提取 Cookie（首次或过期时）

```bash
python get_all_cookies.py --force
```

自动打开浏览器 → 完成 CAS 登录 → 保存 cookie 到 `./seu_cookies.json`。

### 2. 搜索课程

```bash
python scrape.py --search 统一机器人
```

输出所有匹配课程和 teclId：

```
课程名                         编号        teclId   教师
统一机器人学Ⅰ                  B6210100   149550   王玉娟
统一机器人学Ⅰ                  B6210100   149551   魏志勇, 司伟
统一机器人学Ⅰ                  B6210100   149552   毕可东, 阚亚鲸
```

### 3. 下载字幕

```bash
# 首次运行——查看周次分布
python scrape.py 149550 统一机器人学Ⅰ 王玉娟

# 全部下载
python scrape.py 149550 统一机器人学Ⅰ 王玉娟 --weeks 1-14

# 只下前 5 周
python scrape.py 149550 统一机器人学Ⅰ 王玉娟 --weeks 1-5

# 只看不下载
python scrape.py 149550 统一机器人学Ⅰ 王玉娟 --dry-run
```

输出结构：

```
桌面/统一机器人学Ⅰ_王玉娟_字幕爬取/
├── 第1周_周二_第3节/
│   └── 2026-03-03_字幕.txt
├── 第1周_周二_第4节/
│   └── 2026-03-03_字幕.txt
└── ...
```

### 4. 备考大纲（可选）

字幕下载完成后脚本会询问是否生成备考大纲。选择"是"则自动扫描全部字幕，提取：

- 考试形式、题型、分值
- 明确会考/不考的知识点
- 老师说的重点和复习建议

输出 `{课程名}_备考大纲.md` 到桌面。

## 依赖

| 依赖 | 说明 |
|------|------|
| Python 3.8+ | `requests` + `websocket-client` |
| Chromium 浏览器 | Edge / Chrome / Brave / Arc |
| SEU VPN | aTrust |

## 常见问题

**Q: 字幕质量如何？**  
AI 语音识别自动生成，有口音/噪音误差。约 2-5% 的课无实质内容（习题课/调课）。

**Q: Cookie 多久过期？**  
约 30 分钟（CAS maxAge=1800s）。过期后重跑 `get_all_cookies.py --force`。

**Q: 能爬没选的课吗？**  
能。搜索 API 不受选课限制，任何 teclId 都能下载。

## 目录结构

```
├── scrape.py              # 字幕下载 + 搜索
├── get_all_cookies.py     # CDP Cookie 提取
├── SKILL.md               # Claude Code Skill 定义
├── references/
│   └── api-reference.md   # API 手册
├── requirements.txt
├── LICENSE
└── .gitignore
```

## License

MIT
