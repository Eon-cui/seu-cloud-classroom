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

## 命令行速查

```bash
python scrape.py --search 统一机器人                      # 搜课程，拿 teclId
python scrape.py --search 统一机器人 --teacher 祝小元     # 搜 + 教师过滤
python scrape.py 159915 统一机器人学Ⅱ 祝小元 --dry-run    # 只看节次/周次，不下载
python scrape.py 159915 统一机器人学Ⅱ 祝小元 --weeks 1-7  # 下载第 1~7 周
python scrape.py 159915 统一机器人学Ⅱ 祝小元 --diagnose   # 逐节看转写状态
python scrape.py 159915 统一机器人学Ⅱ 祝小元 --weeks 6-7 --resume   # 补漏，已有的跳过
python scrape.py 159915 统一机器人学Ⅱ 祝小元 --weeks 1-7 --out D:\字幕  # 换输出目录

python get_all_cookies.py          # Cookie 过期时用：另开独立窗口登录，不杀你正在用的浏览器
```

## Cookie 说明

Chromium **136+**（Edge 136+ / Chrome 136+）对**默认 profile** 关掉了 `--remote-debugging-port`，
所以"先把浏览器杀干净再带端口重开"的老办法已经拿不到 CDP 端口。

`get_all_cookies.py` 改用**独立 profile** 另开一个窗口：

- 不影响你平时开着的浏览器，也不关任何窗口
- 登录态留在独立 profile 里（`%LOCALAPPDATA%\seu-cloud-classroom\cdp-profile`），下次不用重新登
- 取完自动打 `/authority/me` 校验，通过才说成功

## 字幕为什么是空的？

不是脚本的锅，先看服务端状态：

| `transcriptOptimizeTaskStatus` | 含义 |
|---|---|
| `0` / `1` | 平台还没转写完/排队中 → 过几天 `--resume` 重跑 |
| `3` / `6` | 转写完成 |
| `4` | 转写失败，只能等平台侧重跑 |
| 缺失 | 旧数据，已完成 |

`python scrape.py <teclId> <课程> <教师> --diagnose` 就是干这个的，跑完下载脚本也会自动按状态汇总。

## 字幕质量

AI 语音识别自动转录，老师口音重或环境吵会有些误差，但整体完全可接受。


## 项目结构

```
seu-cloud-classroom/
├── scrape.py                # 主脚本：搜索课程 + 下载字幕 + 周次过滤 + 诊断/续爬
├── get_all_cookies.py       # CDP 提取浏览器 Cookie（独立 profile，跨平台）
├── skill.md                 # Skill 指令（给 AI 看的）
├── references/
│   └── api-reference.md     # 云课堂 API 逆向文档
├── requirements.txt         # Python 依赖
├── LICENSE                  # MIT
├── .gitignore               # 排除 cookie 文件 + 临时文件
├── .gitattributes           # 统一 LF 行尾
└── README.md                # 你正在看的
```

## License

MIT
