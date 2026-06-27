# seu-cloud-classroom

东南大学云课堂 (cvs.seu.edu.cn) 字幕下载工具。

## 功能

- 一键下载课程全部字幕（AI 语音识别文本）
- CDP 自动提取浏览器 Cookie（无需手动 F12 复制）
- 跨平台：Windows / macOS / Linux，Edge / Chrome 全支持

## 安装

```bash
git clone https://github.com/YOUR_USERNAME/seu-cloud-classroom.git
cd seu-cloud-classroom
pip install -r requirements.txt
```

## 使用

### 1. 提取 Cookie（首次或过期时）

```bash
python get_all_cookies.py
```

脚本自动打开浏览器 → 你完成 CAS 登录 → 自动保存 cookie 到 `seu_cookies.json`。

> 需 SEU VPN（aTrust）已连接。

### 2. 下载字幕

```bash
python scrape.py <teclId> <课程名> [教师名]
```

示例：
```bash
python scrape.py 149551 统一机器人学1 司伟
```

字幕保存到桌面 `{课程名}_{教师名}_字幕爬取/` 目录，两级结构：

```
统一机器人学1_司伟_字幕爬取/
├── 第14周_周四_第8节/
│   └── 2026-06-04_字幕.txt
├── 第14周_周四_第7节/
│   └── 2026-06-04_字幕.txt
└── ...
```

### 3. 如何获取 teclId

在浏览器打开课程播放页，从 URL 中提取：
```
https://cvs.seu.edu.cn/.../#/play-center?teclId=149551&...
                                             ^^^^^^
```

## 依赖

| 依赖 | 说明 |
|------|------|
| Python 3.8+ | `requests` + `websocket-client` |
| Chromium 浏览器 | Edge / Chrome / Brave / Arc（CDP 协议） |
| SEU VPN | aTrust，访问 `cvs.seu.edu.cn` |

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 2 | VPN 未连接 |
| 3 | Cookie 过期 |
| 4 | teclId 无效 |
| 5 | 部分失败 |

## 目录结构

```
├── scrape.py            # 字幕下载
├── get_all_cookies.py   # CDP Cookie 提取
├── SKILL.md             # Claude Code Skill 定义
├── references/
│   └── api-reference.md # API 手册
├── requirements.txt
└── .gitignore
```

## License

MIT
