# 东大云课堂 API 详细手册

## 架构

```
用户浏览器 → CAS SSO → cvs.seu.edu.cn (Vue SPA)
                         ├── /jy-application-resourcemanage/ (API 网关)
                         └── /jy-application-resourcemanage-ui/ (静态资源)

视频文件 → dncvsvod.seu.edu.cn (独立 VOD 服务器)
```

网络要求：须连 SEU VPN（aTrust），否则所有请求 `ERR_CONNECTION_CLOSED`。

## 认证机制

- 登录：CAS SSO → OAuth2 code → redirect → JWT (sessionStorage)
- API 访问：5 个 cookie
  - `007d0115-...` + `route`: path=/
  - `jy-application-resourcemanage` + `_bl_usercode` + `_bl_dept`: path=/jy-application-resourcemanage/
- 字幕 API 不需要 JWT 头，仅 cookie 即可
- cookie 有时效（CAS maxAge=1800s），过期需重新登录

## Cookie 提取

### 方法 1: CDP 自动提取（推荐）

```powershell
# 1. 连 VPN 后重启 Edge
Get-Process msedge | Stop-Process -Force
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  -ArgumentList "--remote-debugging-port=9222", "--remote-allow-origins=*", `
  "https://cvs.seu.edu.cn/jy-application-resourcemanage-ui/"

# 2. 用户在 Edge 完成 CAS 登录

# 3. 提取 cookie
python get_all_cookies.py
```

**CDP 关键坑**:
- 必须 `Network.getAllCookies`（不是 `getCookies`）——3 个 cookie path 是 `/jy-application-resourcemanage/`
- Edge 必须在 VPN 之后启动
- `--remote-allow-origins=*` 必须

### 方法 2: 手动复制

F12 → Application → Cookies → `cvs.seu.edu.cn`，复制 5 个 name=value。

## 完整 API 列表

API 前缀: `https://cvs.seu.edu.cn/jy-application-resourcemanage`

### 课程数据

| 端点 | 方法 | 关键参数 | 返回 |
|------|------|------|------|
| `/v1/subject_vod_list_new` | GET | `teclIds`, `page.pageIndex`, `page.pageSize` | `{data: {records: [...], rowCount: N, pageCount: N}}` |
| `/v1/group_subject_vod_list` | GET | `subjName`, `page.*` | 搜索全部教学班，不受选课限制 |

### 字幕

| 端点 | 方法 | 参数 | 返回 |
|------|------|------|------|
| `/v1/course_vod_subtitle` | GET | `courseId={record.id}` | `{data: [{bg, ed, res, courId, transferType}]}` |

`transferType=1` = AI 语音识别。`id` 是负数（Snowflake ID）。

### 播放相关

| 端点 | 方法 | 参数 |
|------|------|------|
| `/v1/vod/playCount` | GET | `id={recordId}` |
| `/v1/vod/keepAlive` | POST | `{"courId": recordId}` |

### 资源下载

| 端点 | 方法 | 参数 |
|------|------|------|
| `/v1/resource/downLoad` | GET | `id`, `vodId`, `fileName` |
| `/v1/resource/pack/downLoad` | GET | `ids`, `vodIds`, `courName` |

### 配置 & 用户

| 端点 | 说明 |
|------|------|
| `/authority/me` | 用户权限（测 cookie 有效性） |
| `/v1/app/info` | 应用信息 |
| `/v1/list/termYear` | 学年学期 |

### 参数名陷阱

| API | 参数名 | 备注 |
|-----|--------|------|
| 字幕 | `courseId` | 全拼 |
| 心跳 | `courId` | 缩写 |
| 播放计数 | `id` | 最短 |

## subject_vod_list_new 返回记录字段

关键字段：
```
id: str              → 字幕 API 的 courseId 参数
teclId: str          → 教学班 ID
subjId: str          → 科目 ID（如 17071）
subjName: str        → 课程名（如"统一机器人学Ⅰ"）
teacNames: [str]     → 本节教师
teclTeacNames: [str] → 教学班全部教师
letiId: int          → 节次 ID
letiNumber: int      → 节次编号（1, 2, 3...）
courBeginTime: str   → 上课时间
courEndTime: str     → 下课时间
clroName: str        → 教室名
orgaNames: [str]     → 开课学院
coursePptSliceStatus: int → PPT 切片状态（5=已处理）
vodStatus: int       → 点播状态（5=就绪）
vodDisplayStatus: int → 显示状态（5=显示）
```

## VOD 服务器

- 域名：`dncvsvod.seu.edu.cn`
- 认证：接受 `cvs.seu.edu.cn` 的 cookie
- 视频路径格式：`/storage-3/vod4/{deviceId}/{date}/CloudIPC-{courseId}-{A}-{B}/{timestamp}.mp4`
- 所有非存在文件返回 `OK`（2 字节），不是 404

## 已知课程

使用 `scrape.py --search <关键词>` 搜索，不维护静态列表。
