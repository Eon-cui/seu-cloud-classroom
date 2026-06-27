---
name: seu-cloud-classroom
description: >
  爬取东南大学云课堂 (cvs.seu.edu.cn) 课程字幕。
  触发：东大云课堂、SEU 网课、爬字幕、cvs.seu.edu.cn、统一机器人、云课堂爬虫。
  用法：用户说"爬{课程名}（{教师名}）的课"→自动完成全部流程。
---

# 东南大学云课堂爬虫

## 平台特征

- **域名**: `cvs.seu.edu.cn`（主站）、`dncvsvod.seu.edu.cn`（视频存储）
- **架构**: SPA（Vue + webpack code splitting，JS bundle 名随部署变）
- **认证**: CAS SSO → OAuth2 → JWT。API 靠 cookie 维持登录态，5 个关键 cookie
- **网络**: 须连 SEU VPN（aTrust），否则 `ERR_CONNECTION_CLOSED`

## 工作流（给 AI 的指令）

用户给课程名 → 你自动执行以下步骤。**每个步骤用现有的 Python 脚本，不要重写。**

**核心原则——不留中间产物**：
- 调试脚本、截图、临时 JSON——任务完成后立即 `Remove-Item`
- 只保留：`seu_cookies.json`（凭证）、字幕文件（用户要的产出）、备考大纲（用户要的产出）
- Python `__pycache__/` 每次跑完清掉

### 步骤 0：检查环境

`scrape.py` 内置三道检测——运行即检测，失败自动报原因：

```bash
python scrape.py <teclId> <课程名> <教师名>
```

**退出码含义 + AI 应对**:

| 码 | 含义 | AI 应做 |
|----|------|---------|
| 0 | 成功 | 报告结果 |
| 1 | 参数缺失 | 检查参数 |
| 2 | VPN 未连接 | 提醒用户连接 SEU VPN，等待确认后重试 |
| 3 | Cookie 过期 | 问用户"要重新提取 Cookie 吗？（会关闭浏览器）"→ 确认后跑 `get_all_cookies.py --force` |
| 4 | teclId 无效 | 让用户在浏览器打开课程页，从 URL 提取 teclId |
| 5 | 部分失败 | 报告失败数量，建议重试 |
| 6 | 未指定周次 | **显示周次分布后，问用户要爬第几周到第几周，拿到答案后加 `--weeks` 重跑** |
| 7 | 缺少 --force | `get_all_cookies.py` 需要 `--force` 才会杀浏览器。先问用户确认 |

### 步骤 1：拿 Cookie

检查 `seu_cookies.json` 存在（脚本同级目录）→ 直接跑 `scrape.py`。
若 `scrape.py` 退出码=3（Cookie 过期），自动执行：

```bash
python get_all_cookies.py --force
```

脚本自动：检测 OS → 找 Edge/Chrome → 关旧实例 → 开 CDP → 打开 SEU → 等用户登录 → 保存 cookie。
**注意**: 必须先问用户"会关闭浏览器，确定？"，确认后才加 `--force`。

**支持**: Windows / macOS / Linux，Edge / Chrome / Chromium 全兼容。

### 步骤 2：找 teclId

**用户给课程名 → 自动搜索**：

```bash
python scrape.py --search <课程关键词>
```

搜索 `subject_vod_list_new?subjName=关键词`，返回匹配课程列表：
```
课程名                           teclId   教师                  学院
------------------------------------------------------------------------------------------
统一机器人学Ⅰ                    149551   魏志勇, 司伟           未来技术学院
```

**只有一个匹配** → 直接用那个 teclId。
**多个匹配** → 列出让用户选。
**搜索不到** → 让用户在浏览器打开课程页，从 URL 提取 teclId。

### 步骤 3：确认周次 + 下载

**首次运行不带 `--weeks`**——脚本打印周次分布后 exit 6：

```bash
python scrape.py <teclId> <课程名> <教师名>
# → exit 6 → 显示周次分布图 →
#   AI 问用户："共14周，要爬第几周到第几周？"
#   用户回复 → AI 加 --weeks 重跑
```

**用户指定后**：
```bash
python scrape.py <teclId> <课程名> <教师名> --weeks 1-5   # 第1~5周
python scrape.py <teclId> <课程名> <教师名> --weeks 3,7    # 第3、7周
```

**只看不下载**：
```bash
python scrape.py <teclId> <课程名> <教师名> --dry-run
```

输出：`~/Desktop/{课程名}_{教师名}_字幕爬取/`，每节课一个子目录 `第X周_周X_第X节/`，内含 `YYYY-MM-DD_字幕.txt`。

如果脚本不存在或参数变了，直接内联 Python（见下方"字幕下载代码"）。

### 步骤 4：备考大纲（可选）

字幕下载完成后，**主动问用户**："是否生成备考大纲？"

**用户说"是"** → 执行以下步骤：

#### 4a. 搜索考试关键词

对字幕目录跑 Grep，搜老师提到的考试相关语句：

```bash
# 搜索所有字幕文件中的考试关键词
grep -n -i "考试\|考\|不考\|重点\|考点\|公式\|会给\|必考\|可能考\|期中\|期末\|小测\|测验\|记住\|掌握\|了解\|不用记\|注意\|占分\|题型" <字幕目录>/*/*.txt
```

**关键词优先级**:

| 优先级 | 关键词 | 含义 |
|--------|--------|------|
| 🔴 必抓 | `不考` `不会考` `不用` `不要求` | 明确排除范围 |
| 🔴 必抓 | `一定考` `必考` `重点` `肯定会` | 明确考试内容 |
| 🟡 重要 | `会给公式` `会给` `可以带` `开卷` `闭卷` | 考试形式/资源 |
| 🟡 重要 | `占.*分` `题型` `选择` `填空` `简答` `计算` `证明` | 题型和分值 |
| 🟢 补充 | `记住` `掌握` `了解` `注意` | 掌握程度要求 |
| 🟢 补充 | `期中` `期末` `小测` `测验` `考试` | 考试时间/范围 |

#### 4b. 精读命中片段

对每个命中的文件，Read 命中行 ±10 行上下文，提取：
- 老师说"不考"的具体内容
- 老师说"会考/重点"的具体内容
- 公式/定理/知识点名称
- 题型、分值、考试形式

#### 4c. 生成大纲

在桌面生成 `{课程名}_{类型}_备考大纲.md`。

自动判定考试类型：
- 如果命中"期中" → `期中备考大纲`
- 如果命中"期末" → `期末备考大纲`
- 如果命中"小测" `测验` → `小测备考大纲`
- 如果都没命中 → 问用户是什么考试

**大纲模板**（严格遵循此结构）：

```markdown
# {课程名} {考试类型}备考大纲

> 基于 SEU 云课堂字幕自动提取 | 生成日期: {今天}

## 考试基本信息

- 形式: {开卷/闭卷/半开卷，从字幕提取}
- 题型: {选择/填空/简答/计算/证明，从字幕提取}
- 分值: {各题型分值，从字幕提取}

## 考试范围（会考什么）

| 知识点 | 章节/周次 | 掌握程度 | 备注 |
|--------|-----------|----------|------|
| xxx | 第x周 | 掌握/了解 | 老师说"重点" |

## 不考范围（明确排除）

| 不考内容 | 章节/周次 | 老师说 | 备注 |
|----------|-----------|--------|------|
| xxx | 第x周 | "这个不考" | |

## 考试会给的资源

| 资源 | 说明 | 来源 |
|------|------|------|
| 公式表 | 会给哪些公式 | 第x周老师提到 |

## 复习建议

{根据老师强调的重点给出 3-5 条建议}

## 数据来源

- 周次范围: 第X~Y周
- 命中考试关键词: X 处
```

#### 4d. 诚实原则

- 如果字幕中**没有**找到考试相关信息 → 直接告诉用户"没找到"，不要编造
- 不确定的内容标注 `[待确认]`
- 区分"老师明确说的"和"AI 推测的"
- 每条结论标注来源（第几周第几节）

## 已保存的 Cookie

位置：脚本同级目录 `./seu_cookies.json`

5 个 cookie：
```json
{
  "007d0115-a0c0-4713-a023-75bc0ff16a59": "...",
  "route": "...",
  "jy-application-resourcemanage": "...",
  "_bl_usercode": "...",
  "_bl_dept": "..."
}
```

前 2 个 `path=/`，后 3 个 `path=/jy-application-resourcemanage/`。Python `requests.Session().cookies.update()` 不区分 path，都能用。

## API 参考

API 前缀：`https://cvs.seu.edu.cn/jy-application-resourcemanage`

| API | 参数 | 用途 |
|-----|------|------|
| `/v1/subject_vod_list_new` | `teclIds`, `page.*` | 课程节次列表 |
| `/v1/course_vod_subtitle` | `courseId={recordId}` | 字幕 JSON |
| `/v1/vod/playCount` | `id={recordId}` | 播放次数 |
| `/v1/vod/keepAlive` | POST `{"courId": recordId}` | 心跳 |
| `/authority/me` | — | 用户权限（测 cookie 有效性） |

**参数名陷阱**: 字幕用 `courseId`（全拼），keepAlive 用 `courId`（缩写），playCount 用 `id`。

### subject_vod_list_new 返回记录关键字段

- `id`: 课程记录 ID → 字幕 API 的 `courseId` 参数
- `letiNumber`: 节次编号（如 1, 2, 3...）
- `courBeginTime` / `courEndTime`: 上课时间
- `subjName`: 课程名
- `teacNames`: 教师名数组
- `teclTeacNames`: 教学班所有教师
- `clroName`: 教室名

### 字幕 JSON 结构

```json
{"data": [{"bg": 开始毫秒, "ed": 结束毫秒, "res": "文本", "transferType": 1}]}
```

`transferType=1` = AI 语音识别生成。

## 字幕下载代码

如果 `scrape.py` 不可用，**读取 scrape.py 源码直接执行**（不要用内联版——内联版过时且功能不全）。

## 已知课程

| 课程 | teclId | 教师 | 节数 |
|------|--------|------|------|
| 统一机器人学1 | 149551 | 司伟, 魏志勇 | 84 |

## 常见坑

1. **Python 版本**: Windows 上 `python`（3.13），不用 `python3`（3.14 有代理 bug）。`s.trust_env = False`
2. **Cookie path**: 3 个 cookie path 是 `/jy-application-resourcemanage/`。CDP 用 `Network.getAllCookies`
3. **VPN**: 必须先连。浏览器在 VPN 之后启动，否则 `ERR_CONNECTION_CLOSED`
4. **JS bundle 名随部署变**: 不硬编码。API 端点稳定，沿用已知列表
5. **参数名**: courseId（字幕）vs courId（心跳）vs id（播放计数），不一致
6. **跨平台**: `get_all_cookies.py` 自动检测 Edge/Chrome 路径和平台，一行命令搞定
7. **PowerShell 内联 Python**: 引号冲突，超过 10 行写成 .py 文件再跑
8. **无字幕**: 纯板书课/设备故障，约占 2-3%
9. **清理中间产物**: 任务完成立即删除临时脚本/截图/JSON，只留 cookie + 字幕 + 大纲
