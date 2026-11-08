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

`scrape.py` 内置三道检测——运行即检测，失败自动报原因。

**VPN 检查**: `check_vpn()` 内部创建独立 Session（`trust_env=False`），不依赖全局 requests 状态。如果 VPN 频繁断连，提示用户检查 aTrust 客户端稳定性。

```bash
python scrape.py <teclId> <课程名> <教师名>
```

**退出码含义 + AI 应对**:

| 码 | 含义 | AI 应做 |
|----|------|---------|
| 0 | 成功 | 报告结果；若有"空"的节，按下面「空字幕归因」解释 |
| 1 | 参数缺失 | 检查参数 |
| 2 | VPN 未连接 | 提醒用户连接 SEU VPN，等待确认后重试 |
| 3 | Cookie 过期 | 直接跑 `python get_all_cookies.py`（**不用杀浏览器**），让用户在弹窗里登录 |
| 4 | teclId 无效 | 让用户在浏览器打开课程页，从 URL 提取 teclId |
| 5 | 部分失败 | 报告失败数量，用 `--resume` 重跑补漏 |
| 6 | 未指定周次 | **显示周次分布后，问用户要爬第几周到第几周，拿到答案后加 `--weeks` 重跑** |

`get_all_cookies.py` 自己也有退出码：`0` 成功 / `1` 没浏览器 / `2` 等待登录超时 / `3` CDP 端口起不来 / `8` cookie 取不全。

### 步骤 1：拿 Cookie

检查 `seu_cookies.json` 存在（脚本同级目录）→ 直接跑 `scrape.py`。
若 `scrape.py` 退出码=3（Cookie 过期），执行：

```bash
python get_all_cookies.py
```

脚本自动：检测 OS → 找 Edge/Chrome → **用独立 profile 另开一个窗口**（不动用户正在用的浏览器）→
打开 SEU 登录页 → 等用户登录 → 取 5 个 cookie → 写 `seu_cookies.json` → 打 `/authority/me` 校验。

**关键**：Chromium 136+（Edge 136+ / Chrome 136+）对**默认 profile** 禁用了 `--remote-debugging-port`，
所以"杀掉浏览器再带端口重开"的老办法已经拿不到 CDP。本脚本用独立 profile 规避：
登录态留在这个 profile 里，下次直接复用，用户不用重复登录。
默认位置 `%LOCALAPPDATA%\seu-cloud-classroom\cdp-profile`（macOS/Linux 见脚本内 `default_profile()`）。

其它用法：
- `--attach`：已有带 CDP 的浏览器在跑时直接取，不开新窗口（自动化流水线用）
- `--profile DIR`：指定 profile 目录
- `--port 9222` / `--browser chrome` / `--timeout 900`
- `--force`：旧行为，关闭所有 Edge/Chrome 再连；**只有 profile 全被占用、窗口起不来时才考虑**，且要先问用户

**支持**: Windows / macOS / Linux，Edge / Chrome / Chromium 全兼容。

### 步骤 2：找 teclId（二级筛选）

**用户给课程名 → 自动搜索。通用原则：搜出来多结果就逐级缩小，让用户选，不要替用户做决定。**

#### 第一级：搜课程

```bash
python scrape.py --search <课程关键词>
# 如果用户说了教师名  → 加 --teacher <教师名>
python scrape.py --search <课程关键词> --teacher <教师名>
```

搜索返回全部教学班，列序号、teclId、学年、教师、课程名：

```
#  teclId   学年         教师                  课程名
------------------------------------------------------------------------------------------
1  149573   2025-2026    汤新华                 信息通信网络概论（全英文）
2  148632   2024-2025    汤新华                 信息通信网络概论（全英文）
3  150795   2025-2026    周波, 张蔚萍            信息通信网络概论
```

#### 第二级：按教师筛选

**如果用户没提教师名，且搜索结果出现多个不同教师** → 列出教师名单，问用户选哪个：

> 搜到 X 位老师的课：汤新华、周波、张蔚萍、吴乐南... 你要哪位老师的？

等用户回答 → 用 `--teacher` 再搜，或直接从已有结果过滤。

**如果用户一开始就说了教师名** → 直接用 `--teacher` 参数，跳过这步。

#### 第三级：按学期筛选

**同一教师可能有多个学期** → 列出学年，问用户选哪个：

> 汤新华有三个学期的课：2025-2026、2024-2025、2022-2023。你要哪个学期的？

等用户回答 → 拿到确定的 teclId。

#### 快速路径

**只有一个匹配** → 直接用那个 teclId，不需要问。
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

**查为什么某些节没字幕**（只读，逐节打印服务端转写状态）：
```bash
python scrape.py <teclId> <课程名> <教师名> --diagnose
python scrape.py <teclId> <课程名> <教师名> --weeks 6-7 --diagnose
```

**断点续爬 / 自定义目录**：
```bash
python scrape.py <teclId> <课程名> <教师名> --weeks 1-7 --resume         # 本地已有的跳过
python scrape.py <teclId> <课程名> <教师名> --weeks 1-7 --out D:\课程字幕  # 不用桌面
```

输出：`~/Desktop/{课程名}_{教师名}_字幕爬取/`，每节课一个子目录 `第X周_周X_第X节/`，内含 `YYYY-MM-DD_字幕.txt`。

#### 空字幕归因（重要，别误判成爬虫 bug）

接口对没转写的节返回 `{"data": []}`（HTTP 200、`dataOk: true`），脚本会标"空"。
判断依据是记录里的 `transcriptOptimizeTaskStatus`，脚本已翻译成中文打印：

| 值 | 含义 | 处置 |
|----|------|------|
| `0` | 转写未开始/排队中 | 平台侧还没跑，过几天 `--resume` 重跑 |
| `1` | 转写中 | 同上，等 |
| `3` / `6` | 转写完成（普通 / 优化版） | 应该有字幕；若仍空，才怀疑脚本 |
| `4` | 转写失败/待重试 | 只能等平台侧重跑，催老师没用就去教务处 |
| 缺失 | 旧数据，已完成 | 应该有字幕 |

脚本跑完会在结尾自动按状态汇总空的节，并给出补跑命令（带 `--resume`）。

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
| `/v1/group_subject_vod_list` | `subjName`, `page.*` | 搜索全部教学班 |
| `/v1/subject_vod_list_new` | `teclIds`, `page.*` | 课程节次列表（下载用） |
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
- `courVodOpen`: 录像是否开放（1=有录像）
- `transcriptOptimizeTaskStatus`: 转写任务状态（见上文「空字幕归因」）

### 字幕 JSON 结构

```json
{"data": [{"bg": 开始毫秒, "ed": 结束毫秒, "res": "文本", "transferType": 1}]}
```

`transferType=1` = AI 语音识别生成。没转写的节返回 `{"data": [], "dataOk": true, "ok": true}`。

## 字幕下载代码

如果 `scrape.py` 不可用，**读取 scrape.py 源码直接执行**（不要用内联版——内联版过时且功能不全）。

## 常见坑

### 环境
1. **Python 版本**: 用 3.13（`py -3.13`）。若 `python` 已指向 3.14，别直接用——3.14 有代理/编码怪问题；至少保持 `s.trust_env = False`
2. **VPN 不稳**: 断连导致 DNS 解析失败（`getaddrinfo failed`）。`check_vpn()` 用 Session（不用裸 `requests.get`），系统代理会干扰
3. **PowerShell 内联 Python**: 引号冲突。超过 5 行写成 .py 文件再跑
4. **别用 PowerShell 读写含中文的 .py**: `Get-Content`/`Set-Content` 会按 ANSI 解码再写 UTF-8，把中文变成乱码（2026-11 踩过，整个脚本废掉）。改文件用编辑器/`read`+`edit`

### API 端点差异
5. **搜索 vs 下载用不同端点**:
   - `group_subject_vod_list` → 搜索全部教学班（不受选课限制）
   - `subject_vod_list_new` → 下载字幕（需要指定 teclId）
6. **字段名不一致**: `group` 用 `teacNames`，`subject_vod_list_new` 用 `teclTeacNames`
7. **搜索是模糊匹配**: "统一机器人"会命中 Ⅰ/Ⅱ/Ⅲ；"统一机器人学2"（阿拉伯数字）搜不到，要写 `统一机器人学Ⅱ` 或只用"统一机器人"。逐级收窄：课程名 → 教师 → 学期
8. **搜索需翻页**: `pageSize=50`，多页时循环取全量
9. **返回的课程数据按时间倒序**: `records[0]` 是最新一节，不是第一节

### Cookie / 浏览器
10. **CDP 用 `Network.getAllCookies`**（非 `getCookies`）: 3 个 cookie path 是 `/jy-application-resourcemanage/`
11. **Edge/Chrome 136+ 默认 profile 禁用远程调试**: `--remote-debugging-port` 会被静默忽略（端口不监听），杀浏览器重开也没用。必须配独立 `--user-data-dir`
12. **可见窗口的进程别被提前杀掉**: 若在 CI/沙箱/后台任务里启动浏览器，父进程结束可能连带杀掉窗口；用户登录到一半窗口消失就是这个。交互式跑最稳
13. **同 profile 被占用会立即退出**（exit 0 且无端口）: 脚本已内置 profile 后缀重试；实在不行才 `--force`

### 字幕质量 / 缺失
14. **AI 转录误差**: 口音/语速/噪音影响。不可控，不是脚本问题
15. **无实质内容**: 习题课/调课通知/设备故障，占 2-5%，行数 < 50
16. **空字幕优先怀疑平台**: 先跑 `--diagnose` 看 `transcriptOptimizeTaskStatus`，0/1/4 都是服务端的事，别改爬虫

### 善后
17. **清理中间产物**: 任务完成立即删除临时脚本/截图/JSON，只留 cookie + 字幕 + 大纲
