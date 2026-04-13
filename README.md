# OSU! 插件
![:astrbot_plugin_osutrack](https://count.getloli.com/@astrbot_plugin_osutrack?name=astrbot_plugin_osutrack&theme=booru-jaypee&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

> AstrBot Plugin
> 
> 基于 osu!track 与 osu!api 的 OSU! 插件

> [!WARNING]
>
> 项目将快速迭代更新，可能会有不稳定的情况，请注意备份数据。

## ✨ 功能

- [x] 支持通过 OAuth2 认证
- [x] 支持通过 osu!api 查询用户信息、谱面信息、好友列表
- [x] 支持通过 osu!api 搜索谱面集
- [x] 支持通过 osu!api 查询个人最佳/最近成绩、谱面排行、个人谱面成绩
- [x] 支持通过 osu!track 更新成绩统计与查看统计图表
- [x] 支持通过 osu!track 查看历史巅峰排名
- [x] 所有命令均支持中文别名
- [x] 支持 LLM Tool 调用（查询用户、谱面、成绩、排行榜、搜索、Wiki、新闻等 9 项）
- [x] 标准化数据存储路径，自动迁移旧版数据
- [x] osu! API v2 公开端点全覆盖（Rankings、Scores、Matches、Changelog、Comments、Events、News、Wiki、Search、Multiplayer、Teams 等）
- [x] osu! 新闻自动推送（支持实时/定时推送模式）
- [x] 精美图片卡片输出（7 种 HTML 模板，支持配置开关）
- [x] News/Wiki 支持完整 HTML 内容渲染

## 📦 安装

1. 通过 AstrBot 的插件市场安装插件。
2. 或者将插件文件夹放入 AstrBot 的 `plugins` 目录下。

> [!NOTE]
>
> 本插件要求 AstrBot >= 4.9.2

## 🔧 配置

在使用本插件之前，请确保您已经在 [osu! 官方网站](https://osu.ppy.sh/home/account/edit) 上注册了一个 OAuth 应用，并获取了以下参数：

- `client_id`: 您的 OAuth 客户端 ID
- `client_secret`: 您的 OAuth 客户端密钥
- `redirect_uri`: 您的 OAuth 重定向 URI（必须与注册时一致，默认 `http://localhost:7210/`）

![OAuth 配置demo](docs/oauth_config_demo.png)

将这些参数依次填写至 AstrBot 的配置选项中方可正常使用本插件。

### 新闻自动推送（可选）

插件支持 osu! 新闻自动推送功能，有新的 osu! 新闻发布时自动发送到指定群聊/会话。

| 配置项 | 说明 | 默认值 |
| ---- | ---- | ---- |
| `news_push_enabled` | 是否启用新闻推送 | `false` |
| `news_push_mode` | 推送模式：`realtime`（发现即推送）或 `scheduled`（定时推送） | `realtime` |
| `news_push_cron` | 定时推送的 cron 表达式（仅 scheduled 模式） | `0 8 * * *` |
| `news_push_interval` | 新闻检查间隔（分钟） | `10` |
| `news_push_sessions` | 推送目标会话列表 | `[]` |
| `use_image_output` | 是否使用图片卡片输出（关闭后始终使用纯文本） | `true` |

可通过在目标群聊中发送 `/osu news_subscribe` 自动添加当前会话到推送列表。

## 📝 命令

所有命令均注册为 `osu`（别名 `OSU`）命令组下，下列命令说明中将省略掉 `/osu` 前缀。括号内为中文别名。

### 关联账号

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `link` | 绑定、关联 | - | 关联 OSU! 用户到当前平台用户 |
| `unlink` | 解绑、取消关联 | - | 解除关联当前平台用户与 OSU! 用户 |

一个 OSU! 用户可以关联至多个平台用户，但一个平台用户只能关联一个 OSU! 用户

### 用户查询

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `me` | 我、个人 | `[模式]` | 查询本用户的信息 |
| `user` | 玩家、查询 | `<用户名/用户ID> [模式] [类型]` | 查询指定用户的信息 |
| `users` | 批量查询 | - | 查询多名用户的信息 |
| `friend` | 好友 | - | 查询好友状态 |

### 谱面查询

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `map` | 谱面 | `<谱面ID>` | 查询指定谱面的信息 |
| `mapset` | 谱面集 | `<谱面集ID>` | 查询指定谱面集的信息 |
| `mapsets` | - | - | 查询多个谱面集的信息 |
| `search map` | 搜索 谱面 | `<关键词> [单页数量] [页码] [高级搜索]` | 搜索谱面 |

### 成绩查询

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `best` | 最佳、bp | `[模式] [数量]` | 查看个人最佳成绩（默认 5 条，最多 20 条） |
| `recent` | 最近、rp | `[模式] [数量]` | 查看最近游玩成绩（含失败，默认 5 条） |
| `scores` | 谱面排行 | `<谱面ID> [模式]` | 查看谱面排行榜（前 10 名） |
| `score` | 成绩 | `<谱面ID> [模式]` | 查看个人在指定谱面上的成绩和排名 |

### 成绩统计

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `update` | 更新、上传 | `[模式]` | 上传当前用户的成绩到 OSU!track（默认 osu 模式） |
| `chart` | 图表、统计 | `[模式] [天数] [类型]` | 查看成绩统计图表 |
| `peak` | 巅峰、历史最佳 | `[模式]` | 查看历史最佳排名和准确率（来源 OSU!track） |

### 社区与信息

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `ranking` | 排行、排名 | `[模式] [类型]` | 查看排行榜（performance/score/charts/country） |
| `match` | 比赛 | `<比赛ID>` | 查看多人比赛详情 |
| `mp` | 多人、房间 | `[房间ID]` | 查看多人游戏房间，不填则显示列表 |
| `news` | 新闻 | `[文章ID]` | 查看 osu! 新闻列表或文章详情 |
| `wiki` | 百科 | `<路径>` | 查看 osu! Wiki 页面 |
| `changelog` | 更新日志 | `[stream]` | 查看 osu! 客户端更新日志 |
| `team` | 团队 | `<团队ID>` | 查看团队信息和成员 |
| `packs` | 曲包 | `[类型]` | 查看谱面包列表 |
| `fav` | 收藏 | - | 查看个人收藏谱面集 |
| `events` | 事件 | - | 查看最近 osu! 事件流 |

### 新闻推送

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `news_subscribe` | 订阅新闻 | - | 订阅当前会话的 osu! 新闻推送 |
| `news_unsubscribe` | 取消订阅新闻 | - | 取消当前会话的 osu! 新闻推送 |

### 帮助

| 命令 | 别名 | 参数 | 说明 |
| ---- | ---- | ---- | ---- |
| `help` | 帮助 | `[命令]` | 查看帮助信息 |

### LLM 工具

本插件注册了以下 LLM 工具，AI 可自动调用：

| 工具名称 | 说明 |
| ---- | ---- |
| `query_osu_user` | 查询 osu! 玩家信息 |
| `query_osu_beatmap` | 查询 osu! 谱面信息 |
| `query_osu_best_scores` | 查询玩家最佳 (BP) 成绩 |
| `query_osu_recent_scores` | 查询玩家最近游玩成绩 |
| `search_osu_beatmapsets` | 搜索 osu! 谱面集 |
| `query_osu_user_score` | 查询玩家在指定谱面上的成绩 |
| `query_osu_ranking` | 查询全球排行榜 |
| `query_osu_wiki` | 查询 osu! Wiki 页面 |
| `query_osu_news` | 查询 osu! 新闻列表或文章详情 |

## 📔 更新

<details>

<summary>近期更新内容</summary>

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
- 新增 osu! 新闻自动推送功能（支持实时推送和定时推送两种模式）
- 新增 `/osu news_subscribe`（订阅新闻）和 `/osu news_unsubscribe`（取消订阅新闻）命令
- 新增配置项：`news_push_enabled`、`news_push_mode`、`news_push_cron`、`news_push_interval`、`news_push_sessions`
- 新增精美图片卡片输出模式（7 种 HTML 模板），新增配置项 `use_image_output`
- News/Wiki 支持完整 HTML 内容渲染
- 新增 LLM Tool `query_osu_news`
- OAuth scope 增加 `friends.read`
- 修复 `fav` scope 检查、mods 字段兼容性
- 新增依赖 `markdown>=3.4.0`

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

### 优化
- 所有命令处理完成后调用 `event.stop_event()` 阻止事件继续传播
- 补全 `info.yaml` 中缺失的模板文本条目

</details>

详细更新日志请查看 [CHANGELOG.md](docs/CHANGELOG.md)。

## 💗 支持

为我的仓库点一个 ⭐️ ！

[OSU!](https://osu.ppy.sh/) | [OSU! API](https://osu.ppy.sh/docs/index.html) | [osutrack-api](https://github.com/Ameobea/osutrack-api)