# 更新日志

## 0.3.1 - 2026-04-13

### 修复
- 修复 t2i 图片渲染 HTTP 500 错误（PNG 格式与 quality 参数冲突），改用 JPEG quality:80
- 修复 LLM 工具同时发送图片和文本的问题，改为图片成功时仅返回简短确认，失败时回退纯文本
- 修复 OAuth 授权后 `friends.read` scope 丢失的问题（osu! API 不返回 scope 字段时使用请求的 scopes 作为回退）

### 优化
- 消除图片卡片渲染时的大面积空白区域（移除 `background-attachment: fixed`，使用 flex 布局 + `min-height: 100vh`）
- News/Wiki 新增 HTML 内容适配方法 `_adapt_html_content()`，自动清理不安全标签/属性、解析相对图片 URL
- 移除所有内容截断限制（`preview[:300]`、`preview[:800]` 等 6 处），保留模板层 `truncated` 参数

### 功能
- 绑定成功后自动显示用户卡片
- `get_beatmapsets`（批量谱面集查询）新增图片卡片渲染
- `tool_query_wiki`（LLM Wiki 工具）新增图片卡片渲染（Markdown→HTML 转换）
- content_card 模板增强：新增 figure、figcaption、hr、strong、em、video、div 等 HTML 元素样式

## 0.3.0 - 2026-04-13

> [!NOTE]
>
> 项目架构完全重构，SDK 层与客户端层分离。要求 AstrBot >= 4.9.2。

### 重构
- 将 osu! API 和 osutrack API 封装为独立的 SDK 层（`src/osuapi/`、`src/osutrackapi/`）
- 将 Token 管理、OAuth 认证、账号关联、API 调用封装为客户端层（`src/client/`）
- 工具函数移至 `src/utils.py`
- 数据存储路径标准化至 `data/plugin_data/osu/`，支持从旧路径自动迁移

### 修复
- 修复 `get_authorization_url()` 未对 `redirect_uri`、`scope` 等参数进行 URL 编码的问题，改用 `urllib.parse.urlencode()`
- 移除 osu! API v2 已废弃的 `key` 查询参数（`UsersEndpoint.get_user()`）
- 修复 `_format_user_info()` 中仅读取已废弃 `hit_accuracy` 字段的问题，优先使用 `accuracy` 并保留向下兼容
- 修复 `fav` 命令缺少 `need_identify=True` scope 检查的问题
- 修复 mods 字段兼容性：同时支持字典格式 `{"acronym": "HD"}` 和字符串格式 `"HD"`（3 处）

### 功能
- 所有命令（help, link, unlink, me, user, users, friend, map, mapset, mapsets, search, update, chart）新增中文别名支持
- `link`（绑定/关联）命令发送授权链接时自动处理平台 URL 限制（如 QQ 官方机器人）
- 新增 LLM Tool 注册：`query_osu_user`（查询用户）、`query_osu_beatmap`（查询谱面）、`query_osu_best_scores`（查询BP）、`query_osu_recent_scores`（查询最近游玩）、`search_osu_beatmapsets`（搜索谱面）、`query_osu_user_score`（查询谱面成绩）、`query_osu_ranking`（查询排行榜）、`query_osu_wiki`（查询Wiki）
- 增强 `_conf_schema.json` 配置项提示信息（hint、obvious_hint、default）
- `metadata.yaml` 新增 `astrbot_version` 版本约束
- 新增 `/osu best`（别名: 最佳、bp）命令 - 查看个人最佳成绩，支持模式和数量参数
- 新增 `/osu recent`（别名: 最近、rp）命令 - 查看最近游玩成绩（含失败），支持模式和数量参数
- 新增 `/osu scores`（别名: 谱面排行）命令 - 查看指定谱面排行榜前 10 名
- 新增 `/osu score`（别名: 成绩）命令 - 查看个人在指定谱面上的成绩和排名
- 新增 `/osu peak`（别名: 巅峰、历史最佳）命令 - 查看 osutrack 记录的历史最佳全球排名和准确率
- `OsuApiClient` 新增 `get_user_scores()`、`get_beatmap_scores()`、`get_user_beatmap_score()` 方法
- 新增 `_format_score()` 通用成绩格式化方法
- `info.yaml` 新增 `scores.*` 和 `peak.*` 模板条目
- `help.yaml` 新增 BEST、RECENT、SCORES、SCORE、PEAK 帮助条目
- 新增 `/osu ranking`（别名: 排行、排名）命令 - 查看排行榜（performance/score/charts/country）
- 新增 `/osu match`（别名: 比赛）命令 - 查看多人比赛详情
- 新增 `/osu mp`（别名: 多人、房间）命令 - 查看多人游戏房间列表或详情
- 新增 `/osu news`（别名: 新闻）命令 - 查看 osu! 新闻列表或文章详情
- 新增 `/osu wiki`（别名: 百科）命令 - 查看 osu! Wiki 页面
- 新增 `/osu changelog`（别名: 更新日志）命令 - 查看 osu! 客户端更新日志
- 新增 `/osu team`（别名: 团队）命令 - 查看团队信息和成员
- 新增 `/osu packs`（别名: 曲包）命令 - 查看谱面包列表
- 新增 `/osu fav`（别名: 收藏）命令 - 查看个人收藏谱面集
- 新增 `/osu events`（别名: 事件）命令 - 查看最近 osu! 事件流
- `info.yaml` 新增 `ranking.*`、`match.*`、`mp.*`、`news.*`、`wiki.*`、`changelog.*`、`team.*`、`packs.*`、`fav.*`、`events.*` 模板条目
- `help.yaml` 新增 RANKING、MATCH、MP、NEWS、WIKI、CHANGELOG、TEAM、PACKS、FAV、EVENTS 帮助条目
- 新增 osu! 新闻自动推送功能，支持实时推送 (realtime) 和定时推送 (scheduled) 两种模式
- 新增 `/osu news_subscribe`（别名: 订阅新闻）命令 - 订阅当前会话的新闻自动推送
- 新增 `/osu news_unsubscribe`（别名: 取消订阅新闻）命令 - 取消订阅
- 新增配置项：`news_push_enabled`（开关）、`news_push_mode`（推送模式）、`news_push_cron`（定时表达式）、`news_push_interval`（检查间隔）、`news_push_sessions`（目标会话）
- 使用 Client Credentials 授权获取新闻，无需用户绑定即可推送
- 支持通过 AstrBot CronJobManager 进行定时推送调度
- 新增精美图片卡片输出模式，包含 7 种 HTML 模板（user_card、score_card、beatmap_card、list_card、ranking_card、info_card、content_card）
- 新增配置项 `use_image_output`（默认开启），关闭后所有命令回退为纯文本输出
- 所有命令均已适配图片卡片输出
- News 文章详情使用 API 返回的完整 HTML 内容渲染，Wiki 页面通过 `markdown` 库转换为 HTML 渲染
- 新闻列表显示文章 slug/ID，方便用户查看详情或 LLM 追查
- 新增 LLM Tool `query_osu_news`：支持查询新闻列表（返回 ID）或指定文章详情
- OAuth 认证 scope 增加 `friends.read`，支持 link 命令重新授权以补全权限

### SDK 端点扩展
- 新增 `RankingsEndpoint`：排名查询（`/rankings/{mode}/{type}`）、Kudosu 排名、Spotlights
- 新增 `ScoresEndpoint`：成绩流查询（`/scores`）、单条成绩详情（`/scores/{score}`）
- 新增 `MatchesEndpoint`：多人比赛列表与详情（`/matches`）
- 新增 `ChangelogEndpoint`：更新日志（`/changelog`）、构建版本查询与检索
- 新增 `CommentsEndpoint`：评论列表与详情（`/comments`）
- 新增 `EventsEndpoint`：事件流（`/events`）
- 新增 `NewsEndpoint`：新闻列表与文章详情（`/news`）
- 新增 `WikiEndpoint`：Wiki 页面查询（`/wiki/{locale}/{path}`）
- 新增 `SearchEndpoint`：站内搜索（`/search`）
- 新增 `MultiplayerEndpoint`：多人游戏房间、播放列表成绩、房间排行榜（`/rooms`）
- 新增 `TeamsEndpoint`：团队信息查询（`/teams/{team}`）
- 新增 `MiscEndpoint`：季节背景（`/seasonal-backgrounds`）、谱面标签（`/tags`）
- `BeatmapsEndpoint` 扩展：谱面包列表与详情（`/beatmaps/packs`）
- `UsersEndpoint` 扩展：已通过谱面（`/users/{user}/beatmaps-passed`）、收藏谱面集（`/me/beatmapset-favourites`）
- `OsuClient` 新增 12 个端点访问器
- `OsuApiClient` 新增 30 个高层封装方法

### 依赖
- 新增 `markdown>=3.4.0`

### 优化
- 所有命令处理完成后调用 `event.stop_event()` 阻止事件继续传播
- 补全 `info.yaml` 中缺失的模板文本条目

## 0.2.2 - 2025-11-03

### 功能
- 增加成绩统计图表功能

### 修复
- 增加logo文件等 AstrBot >4.0 适配内容
- 重构信息提示处理逻辑，移除了大部分硬编码提示文本

## 0.2.1 - 2025-08-07

### 功能
- 增加好友查看功能
- 完成谱面查询、搜索功能

## 0.2.0 - 2025-07-25
> [!WARNING]
>
> 代码完全重构，使用新的客户端架构。

### 功能
- 支持通过 OAuth2 认证
- 支持通过 osu!api 查询用户信息
- 支持通过 osu!track 更新成绩

## 0.1.0 - 2025-04-22
- 初始版本发布

### 功能
- 用户查询
- 成绩查询
- 上传成绩至 osu!track