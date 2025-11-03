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
- [x] 支持通过 osu!api 查询用户信息、谱面信息
- [x] 支持通过 osu!track 更新成绩统计 

## 📦 安装

1. 通过 AstrBot 的插件市场安装插件。
2. 或者将插件文件夹放入 AstrBot 的 `plugins` 目录下。

## 🔧 配置

在使用本插件之前，请确保您已经在 [osu! 官方网站](https://osu.ppy.sh/home/account/edit) 上注册了一个 OAuth 应用，并获取了以下参数：

- `client_id`: 您的 OAuth 客户端 ID
- `client_secret`: 您的 OAuth 客户端密钥
- `redirect_uri`: 您的 OAuth 重定向 URI（必须与注册时一致）

![OAuth 配置demo](docs/oauth_config_demo.png)

将这些参数依次填写至 AstrBot 的配置选项中方可正常使用本插件。

## 📝 命令

所有命令均注册为 `osu` 命令组下，下列命令说明中将省略掉 `/osu` 前缀。

### 关联账号

| 命令 | 参数 | 说明 |
| ---- | ---- | ---- |
| `link` | - | 关联 OSU! 用户到当前平台用户 |
| `unlink` | - | 解除关联当前平台用户与 OSU! 用户 |

一个 OSU! 用户可以关联至多个平台用户，但一个平台用户只能关联一个 OSU! 用户

### 用户查询

| 命令 | 参数 | 说明 |
| ---- | ---- | ---- |
| `me` | `[模式]` | 查询本用户的信息 |
| `user` | `<用户名/用户ID> [模式] [类型]` | 查询指定用户的信息 |
| `users` | - | 查询多名用户的信息 |
| `friend` | - | 查询好友状态 |

### 谱面查询

| 命令 | 参数 | 说明 |
| ---- | ---- | ---- |
| `map` | `<谱面ID>` | 查询指定谱面的信息 |
| `mapset` | `<图集ID>` | 查询指定图集的信息 |
| `mapsets` | - | 查询多个图集的信息 |
| `search map` | `<关键词> [单页数量] [页码] [高级搜索]` | 查询谱面 |

### 成绩统计

| 命令 | 参数 | 说明 |
| ---- | ---- | ---- |
| `update` | `[模式]` | 上传当前用户的成绩到 OSU!track（默认 osu 模式） |
| `chart` | `[模式] [天数] [类型]` | 查看成绩统计图表 |

### 帮助

| 命令 | 参数 | 说明 |
| ---- | ---- | ---- |
| `help` | `[命令]` | 查看帮助信息 |

## 📔 更新

<details>

<summary>近期更新内容</summary>

## 0.2.2 - 2025-11-03

### 功能
- 增加成绩统计图表功能

### 修复
- 增加logo文件等 AstrBot >4.0 适配内容
- 重构信息提示处理逻辑，移除了大部分硬编码提示文本

</details>

详细更新日志请查看 [CHANGELOG.md](docs/CHANGELOG.md)。

## 💗 支持

为我的仓库点一个 ⭐️ ！

[OSU!](https://osu.ppy.sh/) | [OSU! API](https://osu.ppy.sh/docs/index.html) | [osutrack-api](https://github.com/Ameobea/osutrack-api)