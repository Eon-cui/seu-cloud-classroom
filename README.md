# seu-cloud-classroom

东南大学云课堂字幕爬虫（两分钟轻松爬取）

> 作者是东大未来技术学院本科生，为准备期末复习而写的。

## 使用

跟 Claude Code / Codex / Trae 等 说 "爬xx课程" → 自动完成：

1. 搜课程 → 找到所有教学班
2. 问你要第几周到第几周 → 下载字幕
3. 问你要不要生成备考大纲 → 扫字幕提取考点

最终交付整理好的字幕文档和备考大纲，落到桌面。


## 爬前准备

- 连接**校园网**或登录**aTrust VPN**
- 使用**Edge 或 Chrome**浏览器 — 首次登录拿 Cookie 用一次，之后复用

## 安装

```bash
git clone https://github.com/Eon-cui/seu-cloud-classroom.git
cd seu-cloud-classroom
pip install -r requirements.txt
```

## 字幕质量

AI 语音识别自动转录，老师口音重或环境吵会有些误差，但整体完全可接受。


## 项目结构

```
seu-cloud-classroom/
├── scrape.py                # 主脚本：搜索课程 + 下载字幕 + 周次过滤
├── get_all_cookies.py       # CDP 自动提取浏览器 Cookie（跨平台）
├── SKILL.md                 # Claude Code Skill 指令（给 AI 看的）
├── references/
│   └── api-reference.md     # 云课堂 API 逆向文档
├── requirements.txt         # Python 依赖
├── LICENSE                  # MIT
├── .gitignore               # 排除 cookie 文件 + 临时文件
└── README.md                # 你正在看的
```

## License

MIT
