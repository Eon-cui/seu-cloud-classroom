# seu-cloud-classroom

东南大学云课堂字幕爬虫——说句话就能把课件字幕扒下来。

> 作者：东大未来技术学院本科生。期末复习时写的，懒得手动翻视频做笔记。

## 能干什么

跟 Claude Code 说 "爬统一机器人学Ⅰ（王玉娟）" → 自动完成：

1. 搜课程 → 找到所有教学班
2. 问你要第几周到第几周 → 下载字幕
3. 问你要不要生成备考大纲 → 扫字幕提取考点

字幕按 **第X周_周X_第X节** 整理，落到桌面。

## 你需要准备

- **SEU VPN (aTrust)** — 连上才能访问云课堂
- **Edge 或 Chrome** — 首次登录拿 Cookie 用一次，之后复用
- **Python 3.8+** — 跑脚本

## 安装

```bash
git clone https://github.com/Eon-cui/seu-cloud-classroom.git
cd seu-cloud-classroom
pip install -r requirements.txt
```

## 怎么用

### 第一步：拿 Cookie（只做一次）

```bash
python get_all_cookies.py --force
```

浏览器弹出来 → 登录 CAS → 自动保存。之后不用再登。

### 第二步：跟 Claude Code 说句话

```
爬统一机器人学Ⅰ（王玉娟）
```

或者手动跑：

```bash
# 搜课程
python scrape.py --search 统一机器人

# 下载（选周次）
python scrape.py 149550 统一机器人学Ⅰ 王玉娟 --weeks 1-14
```

### 第三步：备考大纲

下载完会问"要生成备考大纲吗？"→ 说"是" → 自动扫描字幕，输出：

```
统一机器人学Ⅰ_期末备考大纲.md
  ├── 考试形式、题型、分值
  ├── 老师说会考什么
  ├── 老师明确说不考什么
  └── 复习建议
```

## 输出长这样

```
桌面/统一机器人学Ⅰ_王玉娟_字幕爬取/
├── 第1周_周二_第3节/
│   └── 2026-03-03_字幕.txt
├── 第14周_周四_第8节/
│   └── 2026-06-04_字幕.txt
└── 统一机器人学Ⅰ_期末备考大纲.md
```

## 字幕质量

AI 语音识别自动转录，老师口音重或环境吵会有些误差。习题课/调课那几节基本没内容（占 2-5%），不是脚本的问题。

## 常见问题

**Q: 能爬我没选的课吗？**  
能。搜索不受选课限制。

**Q: Cookie 能管多久？**  
约 30 分钟，过期重跑第一步。

**Q: 不是 Claude Code 能用吗？**  
手动跑命令一样用。只是少了 AI 帮你搜课程、问周次、问大纲的交互。

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

| 文件 | 给谁用 | 作用 |
|------|--------|------|
| `scrape.py` | 人 / AI | `--search` 搜课程，`--weeks` 下周次，`--dry-run` 预览 |
| `get_all_cookies.py` | 人 / AI | 自动开浏览器拿 Cookie，**需 `--force` 确认** |
| `SKILL.md` | Claude Code | 告诉 AI 怎么调用这些脚本、退出码对应什么操作 |
| `api-reference.md` | 开发者 | API 端点、字段名陷阱、字幕 JSON 结构 |

## License

MIT
