from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.util import session_waiter, SessionController
import astrbot.api.message_components as Comp

import os
import json
import urllib.parse
import asyncio
import datetime
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .src.utils import load_help_data, get_info, validate_osu_mode, to_track_mode
from .src.client import LinkAccountManager, OAuthClient, OsuApiClient, TokenManager
from .src.osutrackapi import OsuTrackApi, StatsUpdate, RecordedScore, PeakData

try:
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path
    _DATA_DIR = str(Path(get_astrbot_data_path()) / "plugin_data" / "osu")
except ImportError:
    _PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
    _DATA_DIR = os.path.dirname(_PLUGIN_DIR)


@register("osu", "gameswu", "基于osu!track与osu!api的osu!插件", "0.3.0",
          "https://github.com/gameswu/astrbot_plugin_osutrack")
class OsuTrackPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 数据目录迁移：旧版数据可能在 data/plugins/ 下
        self._migrate_data()

        # 从配置获取 OAuth 设置
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.redirect_uri = config.get("redirect_uri", "http://localhost:7210/")

        # 初始化管理器
        self.token_manager = TokenManager(_DATA_DIR)
        self.link_mgr = LinkAccountManager(_DATA_DIR)
        self.oauth = OAuthClient(
            client_id=self.client_id or 0,
            client_secret=self.client_secret or "",
            redirect_uri=self.redirect_uri,
            token_manager=self.token_manager,
        )
        self.osu = OsuApiClient(self.oauth)
        self.osutrack = OsuTrackApi()

        # 帮助信息
        self.help_data = load_help_data()

        # 图片输出配置
        self._use_image_output: bool = config.get("use_image_output", True)

        # HTML 模板
        self._tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
        self._templates: dict[str, str] = {}
        _all_templates = (
            "user_card", "score_card", "beatmap_card",
            "list_card", "ranking_card", "info_card", "content_card",
        )
        for name in _all_templates:
            path = os.path.join(self._tmpl_dir, f"{name}.html")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self._templates[name] = f.read()

        # 新闻推送
        self._news_push_enabled = config.get("news_push_enabled", False)
        self._news_push_mode = config.get("news_push_mode", "realtime")
        self._news_push_cron = config.get("news_push_cron", "0 8 * * *")
        self._news_push_interval = max(config.get("news_push_interval", 10), 1)
        self._news_push_sessions: list[str] = config.get("news_push_sessions", [])
        self._news_state_file = os.path.join(_DATA_DIR, "news_push_state.json")
        self._news_pending: list[dict] = []  # scheduled 模式下待推送的新闻
        self._news_poll_task: asyncio.Task | None = None
        self._news_cron_job_id: str | None = None
        # 用于 client_credentials 获取新闻的独立 SDK 客户端
        self._news_client: OsuClient | None = None

    async def initialize(self):
        if self._news_push_enabled and self.client_id and self.client_secret:
            await self._start_news_push()

    async def _start_news_push(self):
        """Initialize and start the news push background task."""
        from .src.osuapi import OsuClient
        self._news_client = OsuClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        await self._news_client.client_credentials()
        self._news_poll_task = asyncio.create_task(self._news_poll_loop())

        if self._news_push_mode == "scheduled":
            try:
                self._news_cron_job_id = None
                job = await self.context.cron_manager.add_basic_job(
                    name="osu_news_scheduled_push",
                    cron_expression=self._news_push_cron,
                    handler=self._flush_pending_news,
                    description="osu! 新闻定时推送",
                    timezone="Asia/Shanghai",
                )
                self._news_cron_job_id = job.job_id
                logger.info(f"osu! 新闻定时推送已注册，cron: {self._news_push_cron}")
            except Exception as e:
                logger.error(f"osu! 新闻定时推送注册失败: {e}")

        logger.info(f"osu! 新闻推送已启动 (模式: {self._news_push_mode}, "
                     f"间隔: {self._news_push_interval}分钟, "
                     f"目标会话: {len(self._news_push_sessions)}个)")

    def _load_news_state(self) -> dict:
        if os.path.exists(self._news_state_file):
            with open(self._news_state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_news_state(self, state: dict):
        with open(self._news_state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)

    async def _news_poll_loop(self):
        """Background loop that periodically checks for new osu! news."""
        await asyncio.sleep(5)  # 启动后稍等几秒
        while True:
            try:
                if self._news_push_sessions and self._news_client:
                    await self._check_and_push_news()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"osu! 新闻轮询出错: {e}")
            try:
                await asyncio.sleep(self._news_push_interval * 60)
            except asyncio.CancelledError:
                break

    async def _check_and_push_news(self):
        """Check for new news and push or queue them."""
        # 刷新 client credentials token (if expired)
        try:
            await self._news_client.client_credentials()
        except Exception:
            pass

        data = await self._news_client.news.get_news_listing(limit=5)
        posts = data.get("news_posts", [])
        if not posts:
            return

        state = self._load_news_state()
        last_seen_id = state.get("last_seen_id")
        last_seen_slug = state.get("last_seen_slug")

        new_posts = []
        for post in posts:
            pid = post.get("id")
            slug = post.get("slug", "")
            if last_seen_id and pid and pid <= last_seen_id:
                break
            if last_seen_slug and slug == last_seen_slug:
                break
            new_posts.append(post)

        if not new_posts:
            return

        # 更新 state 为最新的一条
        latest = posts[0]
        state["last_seen_id"] = latest.get("id")
        state["last_seen_slug"] = latest.get("slug", "")
        self._save_news_state(state)

        # 按时间正序推送（最旧的先推）
        new_posts.reverse()

        if self._news_push_mode == "realtime":
            for post in new_posts:
                await self._push_news_to_sessions(post)
                await asyncio.sleep(1)
        else:
            # scheduled 模式: 存入待推送列表
            self._news_pending.extend(new_posts)

    async def _flush_pending_news(self):
        """Flush all pending news (called by cron in scheduled mode)."""
        if not self._news_pending:
            return
        posts = self._news_pending.copy()
        self._news_pending.clear()
        for post in posts:
            await self._push_news_to_sessions(post)
            await asyncio.sleep(1)

    async def _push_news_to_sessions(self, post: dict):
        """Push a single news post to all configured sessions."""
        title = post.get("title", "?")
        author = post.get("author", "?")
        published_at = post.get("published_at", "-")
        preview = post.get("preview", "")
        slug = post.get("slug", "")

        parts = [f"📰 osu! 新闻推送\n"]
        parts.append(f"📌 {title}")
        parts.append(f"✍️ {author} | 📅 {published_at[:10] if published_at else '-'}")
        if preview:
            text = preview[:300]
            if len(preview) > 300:
                text += "..."
            parts.append(f"\n{text}")
        if slug:
            parts.append(f"\n🔗 https://osu.ppy.sh/home/news/{slug}")

        message = MessageChain([Comp.Plain("\n".join(parts))])

        for session_str in self._news_push_sessions:
            try:
                await self.context.send_message(session_str, message)
            except Exception as e:
                logger.warning(f"osu! 新闻推送到 {session_str} 失败: {e}")

    @staticmethod
    def _migrate_data():
        """Migrate data files from old location (data/plugins/) to new (data/plugin_data/osu/)."""
        os.makedirs(_DATA_DIR, exist_ok=True)
        _plugin_dir = os.path.dirname(os.path.abspath(__file__))
        _old_dir = os.path.dirname(_plugin_dir)
        for fname in ("osu_tokens.json", "osuaccount.json"):
            old_path = os.path.join(_old_dir, fname)
            new_path = os.path.join(_DATA_DIR, fname)
            if os.path.exists(old_path) and not os.path.exists(new_path):
                import shutil
                shutil.move(old_path, new_path)
                logger.info(f"osu! 插件: 已迁移 {fname} 至 {_DATA_DIR}")

    @filter.command_group("osu", alias={"OSU"})
    async def osu_group(self, event: AstrMessageEvent):
        pass

    # ================================================================
    # help
    # ================================================================

    @osu_group.command("help", alias={"帮助"})
    async def help_command(self, event: AstrMessageEvent, command: str = None):
        if not self.help_data:
            await event.send(MessageChain([Comp.Plain("❌ 帮助信息加载失败，请联系管理员。")]))
            return

        if command:
            command_key = command.upper()
            help_text = self.help_data.get("commands", {}).get(command_key)
            if help_text:
                final_text = f"OSU! 插件帮助 - /osu {command.lower()}\n\n{help_text}"
            else:
                final_text = f"❌ 未找到命令 '{command}' 的帮助信息。\n\n"
                final_text += self.help_data.get("general", "帮助信息不可用。")
        else:
            final_text = self.help_data.get("general", "帮助信息不可用。")

        await event.send(MessageChain([Comp.Plain(final_text)]))
        event.stop_event()

    # ================================================================
    # link / unlink
    # ================================================================

    @osu_group.command("link", alias={"绑定", "关联"})
    async def link_account(self, event: AstrMessageEvent):
        platform_id = event.get_sender_id()

        existing_osu_id = self.link_mgr.get_osu_id(platform_id)
        is_relink = existing_osu_id is not None

        if not self.client_id or not self.client_secret:
            await event.send(MessageChain([Comp.Plain(get_info("link.config_incomplete"))]))
            return

        try:
            state = f"{platform_id}_{int(asyncio.get_event_loop().time())}"
            all_scopes = ["public", "identify", "friends.read"]
            auth_url = self.oauth.get_authorization_url(state, scopes=all_scopes)
            if is_relink:
                await event.send(MessageChain([Comp.Plain(
                    get_info("link.already_linked", osu_id=existing_osu_id))]))
            try:
                await event.send(MessageChain([Comp.Plain(
                    get_info("link.auth_flow", auth_url=auth_url))]))
            except Exception:
                # 部分平台（如 QQ 官方机器人）禁止消息中包含外部 URL，
                # 对域名做脱敏处理后重发
                sanitized_url = auth_url.replace("osu.ppy.sh", "osu[.]ppy[.]sh")
                await event.send(MessageChain([Comp.Plain(
                    get_info("link.auth_flow_sanitized", auth_url=sanitized_url))]))

            @session_waiter(timeout=300)
            async def handle_auth_callback(controller: SessionController, event: AstrMessageEvent):
                try:
                    callback_url = event.message_str.strip()

                    if "code=" not in callback_url:
                        await event.send(MessageChain([Comp.Plain(get_info("callback.invalid_url"))]))
                        controller.keep(60)
                        return

                    parsed = urllib.parse.urlparse(callback_url)
                    qp = urllib.parse.parse_qs(parsed.query)
                    auth_code = qp.get("code", [None])[0]
                    cb_state = qp.get("state", [None])[0]

                    if not auth_code:
                        await event.send(MessageChain([Comp.Plain(get_info("callback.no_code"))]))
                        controller.keep(60)
                        return

                    if cb_state and not cb_state.startswith(platform_id):
                        await event.send(MessageChain([Comp.Plain(get_info("callback.state_mismatch"))]))
                        controller.stop()
                        return

                    await event.send(MessageChain([Comp.Plain(get_info("common.processing"))]))
                    await self.oauth.exchange_code(auth_code, platform_id)

                    user_info = await self.oauth.get_user_info(platform_id)
                    if not user_info:
                        await event.send(MessageChain([Comp.Plain(get_info("callback.get_user_failed"))]))
                        controller.stop()
                        return

                    osu_uid = user_info["id"]
                    username = user_info["username"]

                    if is_relink:
                        # 重新认证：先解除旧绑定，再建立新绑定
                        self.link_mgr.unlink(platform_id)

                    if self.link_mgr.link(osu_uid, platform_id):
                        await event.send(MessageChain([Comp.Plain(
                            get_info("link.success", username=username,
                                     osu_user_id=osu_uid, platform_id=platform_id))]))
                        logger.info(f"{'重新' if is_relink else ''}关联成功: {username}({osu_uid}) <-> {platform_id}")
                    else:
                        self.oauth.remove_token(platform_id)
                        await event.send(MessageChain([Comp.Plain(
                            get_info("callback.link_failed", platform_id=platform_id))]))

                    controller.stop()
                except Exception as e:
                    logger.error(f"处理 OSU 授权回调失败: {e}")
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="授权", error=str(e)))]))
                    controller.stop()

            try:
                await handle_auth_callback(event)
            except TimeoutError:
                await event.send(MessageChain([Comp.Plain(get_info("callback.timeout"))]))

        except Exception as e:
            logger.error(f"OSU 账号关联过程中发生错误: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="关联", error=str(e)))]))

    @osu_group.command("unlink", alias={"解绑", "取消关联"})
    async def unlink_account(self, event: AstrMessageEvent):
        platform_id = event.get_sender_id()
        existing_osu_id = self.link_mgr.get_osu_id(platform_id)
        if not existing_osu_id:
            await event.send(MessageChain([Comp.Plain(get_info("unlink.not_linked"))]))
            return

        try:
            if self.link_mgr.unlink(platform_id):
                self.oauth.remove_token(platform_id)
                await event.send(MessageChain([Comp.Plain(
                    get_info("unlink.success", osu_id=existing_osu_id))]))
                logger.info(f"解除关联: {existing_osu_id} <-> {platform_id}")
            else:
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.error_generic", operation="解除关联", error="未知错误"))]))
        except Exception as e:
            logger.error(f"解除关联失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="解除关联", error=str(e)))]))

    # ================================================================
    # me / user / users
    # ================================================================

    @osu_group.command("me", alias={"我", "个人"})
    async def get_me(self, event: AstrMessageEvent, mode: str = None):
        auth_ok, platform_id, osu_id = await self._check_auth(event, need_identify=True)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="个人"))]))
            user_info = await self.osu.get_own_data(platform_id, mode)
            # 尝试文转图
            img_url = await self._render_user_card(user_info)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                avatar_url, text = self._format_user_info(user_info, is_self=True)
                chain: list = []
                if avatar_url:
                    chain.append(Comp.Image.fromURL(avatar_url))
                chain.append(Comp.Plain(text))
                await event.send(MessageChain(chain))
        except Exception as e:
            logger.error(f"获取个人信息失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取个人信息", error=str(e)))]))
        event.stop_event()

    @osu_group.command("user", alias={"玩家", "查询"})
    async def get_user(self, event: AstrMessageEvent, user: str, mode: str = None, type: str = None):
        if not user:
            await event.send(MessageChain([Comp.Plain(get_info("user.usage"))]))
            return

        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        if type and type not in ("id", "name"):
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="查询类型", error="无效的查询类型"))]))
            return

        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.querying_user", user=user))]))

            processed_user: str | int = user
            if type == "id":
                if user.isdigit():
                    processed_user = int(user)
                else:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="查询用户",
                                 error=f"指定为 ID 查询，但输入 '{user}' 不是有效的数字ID"))]))
                    return
            elif type == "name":
                if not user.startswith("@"):
                    processed_user = f"@{user}"
            else:
                if user.isdigit():
                    processed_user = int(user)

            user_info = await self.osu.get_user(platform_id, processed_user, mode)
            # 尝试文转图
            img_url = await self._render_user_card(user_info)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                avatar_url, text = self._format_user_info(user_info)
                chain: list = []
                if avatar_url:
                    chain.append(Comp.Image.fromURL(avatar_url))
                chain.append(Comp.Plain(text))
                await event.send(MessageChain(chain))
        except Exception as e:
            logger.error(f"查询用户 {user} 失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="查询用户", error=str(e)))]))
        event.stop_event()

    @osu_group.command("users", alias={"批量查询"})
    async def get_users(self, event: AstrMessageEvent):
        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        await event.send(MessageChain([Comp.Plain(get_info("batch_query.users_prompt"))]))

        @session_waiter(timeout=300)
        async def handle_user_ids_input(controller: SessionController, event: AstrMessageEvent):
            try:
                user_input = event.message_str.strip()
                if user_input.lower() in ("取消", "cancel", "退出", "quit"):
                    await event.send(MessageChain([Comp.Plain(get_info("common.cancel", type="批量查询"))]))
                    controller.stop()
                    return

                user_ids = user_input.split()
                if not user_ids:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="批量查询", error="请提供至少一个用户ID"))]))
                    controller.keep(60)
                    return
                if len(user_ids) > 50:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="批量查询",
                                 error=f"最多支持同时查询 50 个用户\n您提供了 {len(user_ids)} 个用户ID"))]))
                    controller.keep(60)
                    return

                processed = [int(uid) if uid.isdigit() else uid for uid in user_ids if uid.strip()]
                if not processed:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="批量查询", error="没有有效的用户ID"))]))
                    controller.keep(60)
                    return

                await event.send(MessageChain([Comp.Plain(
                    get_info("common.querying", count=len(processed), type="用户"))]))

                users_info = await self.osu.get_users(platform_id, processed)
                if not users_info:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="查询用户", error="没有找到任何用户信息"))]))
                    controller.stop()
                    return

                for i, u in enumerate(users_info, 1):
                    avatar_url, text = self._format_user_info(u)
                    chain: list = []
                    if avatar_url:
                        chain.append(Comp.Image.fromURL(avatar_url))
                    chain.append(Comp.Plain(f"【{i}/{len(users_info)}】\n{text}"))
                    await event.send(MessageChain(chain))
                    if i < len(users_info):
                        await asyncio.sleep(0.5)

                controller.stop()
            except Exception as e:
                logger.error(f"批量查询用户失败: {e}")
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.error_generic", operation="批量查询", error=str(e)))]))
                controller.stop()

        try:
            await handle_user_ids_input(event)
        except TimeoutError:
            await event.send(MessageChain([Comp.Plain(
                get_info("batch_query.timeout", command="users"))]))

    # ================================================================
    # update
    # ================================================================

    @osu_group.command("update", alias={"更新", "上传"})
    async def update(self, event: AstrMessageEvent, mode: str = None):
        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            validated_mode = validate_osu_mode(mode or "osu")
            track_mode = to_track_mode(validated_mode)

            await event.send(MessageChain([Comp.Plain(
                get_info("common.uploading", mode=validated_mode.upper()))]))

            update_resp = await self.osutrack.update_user(osu_id, track_mode)

            await event.send(MessageChain([Comp.Plain(get_info(
                "update.success",
                username=update_resp.username,
                mode=validated_mode.upper(),
                new_hs_count=len(update_resp.newhs),
                pp_change=f"{update_resp.pp_rank:+.2f}" if update_resp.pp_rank is not None else "-",
            ))]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("update.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"上传成绩失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="上传成绩", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # map / mapset / mapsets
    # ================================================================

    @osu_group.command("map", alias={"谱面"})
    async def get_beatmap(self, event: AstrMessageEvent, beatmap_id: str):
        if not beatmap_id:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.map_usage"))]))
            return
        if not beatmap_id.isdigit():
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.invalid_id", id=beatmap_id))]))
            return

        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.querying_beatmap", id=beatmap_id))]))
            bm = await self.osu.get_beatmap(platform_id, int(beatmap_id))
            # 尝试文转图
            img_url = await self._render_beatmap_card(bm=bm)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                await event.send(MessageChain([Comp.Plain(self._format_beatmap_info(bm))]))
        except Exception as e:
            logger.error(f"查询谱面 {beatmap_id} 失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="查询谱面", error=str(e)))]))

    @osu_group.command("mapset", alias={"谱面集"})
    async def get_beatmapset(self, event: AstrMessageEvent, mapset_id: str):
        if not mapset_id:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.mapset_usage"))]))
            return
        if not mapset_id.isdigit():
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.invalid_mapset_id", id=mapset_id))]))
            return

        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.querying_beatmapset", id=mapset_id))]))
            bs = await self.osu.get_beatmapset(platform_id, int(mapset_id))
            # 尝试文转图
            img_url = await self._render_beatmap_card(bs=bs)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                cover_url, text = self._format_beatmapset_info(bs)
                chain: list = []
                if cover_url:
                    chain.append(Comp.Image.fromURL(cover_url))
                chain.append(Comp.Plain(text))
                await event.send(MessageChain(chain))
        except Exception as e:
            logger.error(f"查询谱面集 {mapset_id} 失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                f"❌ 查询谱面集 {mapset_id} 失败: {str(e)}\n请检查谱面集ID是否正确，或稍后重试")]))

    @osu_group.command("mapsets")
    async def get_beatmapsets(self, event: AstrMessageEvent):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        await event.send(MessageChain([Comp.Plain(get_info("batch_query.mapsets_prompt"))]))

        @session_waiter(timeout=300)
        async def handle_mapset_ids_input(controller: SessionController, event: AstrMessageEvent):
            try:
                user_input = event.message_str.strip()
                if user_input.lower() in ("取消", "cancel", "退出", "quit"):
                    await event.send(MessageChain([Comp.Plain(get_info("common.cancel", type="批量查询"))]))
                    controller.stop()
                    return

                mapset_ids = user_input.split()
                if not mapset_ids:
                    await event.send(MessageChain([Comp.Plain(get_info("batch_query.no_ids", type="谱面集"))]))
                    controller.keep(60)
                    return
                if len(mapset_ids) > 20:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("batch_query.too_many", type="谱面集", count=len(mapset_ids), max=20))]))
                    controller.keep(60)
                    return

                valid_ids = [int(mid) for mid in mapset_ids if mid.isdigit()]
                invalid = [mid for mid in mapset_ids if not mid.isdigit()]
                if invalid:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("batch_query.invalid_ids", type="谱面集",
                                 ids=", ".join(invalid), valid_count=len(valid_ids)))]))
                if not valid_ids:
                    await event.send(MessageChain([Comp.Plain(get_info("batch_query.no_valid_ids", type="谱面集"))]))
                    controller.keep(60)
                    return

                await event.send(MessageChain([Comp.Plain(
                    get_info("common.querying", count=len(valid_ids), type="谱面集"))]))

                ok_count, fail_count = 0, 0
                for i, mid in enumerate(valid_ids, 1):
                    try:
                        bs = await self.osu.get_beatmapset(platform_id, mid)
                        cover_url, text = self._format_beatmapset_info(bs)
                        chain: list = []
                        if cover_url:
                            chain.append(Comp.Image.fromURL(cover_url))
                        chain.append(Comp.Plain(f"【{i}/{len(valid_ids)}】\n{text}"))
                        await event.send(MessageChain(chain))
                        ok_count += 1
                        if i < len(valid_ids):
                            await asyncio.sleep(0.5)
                    except Exception as exc:
                        logger.error(f"查询谱面集 {mid} 失败: {exc}")
                        await event.send(MessageChain([Comp.Plain(
                            f"❌ 【{i}/{len(valid_ids)}】查询谱面集 {mid} 失败: {exc}")]))
                        fail_count += 1

                await event.send(MessageChain([Comp.Plain(
                    f"✅ 批量查询完成！成功: {ok_count}, 失败: {fail_count}")]))
                controller.stop()
            except Exception as e:
                logger.error(f"批量查询谱面集失败: {e}")
                await event.send(MessageChain([Comp.Plain(
                    f"❌ 批量查询失败: {str(e)}\n请检查谱面集ID是否正确，或稍后重试")]))
                controller.stop()

        try:
            await handle_mapset_ids_input(event)
        except TimeoutError:
            await event.send(MessageChain([Comp.Plain(
                get_info("batch_query.timeout", command="mapsets"))]))

    # ================================================================
    # friend
    # ================================================================

    @osu_group.command("friend", alias={"好友"})
    async def get_friends(self, event: AstrMessageEvent):
        auth_ok, platform_id, _ = await self._check_auth(event, need_friends=True)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="好友列表"))]))
            friends = await self.osu.get_friends(platform_id)

            if not friends:
                await event.send(MessageChain([Comp.Plain(get_info("friend.empty"))]))
                return

            total = len(friends)
            # 尝试文转图
            items = []
            for i, friend in enumerate(friends[:15], 1):
                username = getattr(friend, "username", "?")
                uid = getattr(friend, "id", "?")
                s = getattr(friend, "statistics", None)
                pp_str = f"{s.pp:.0f}pp" if s and s.pp else ""
                items.append({"index": i, "icon": "👤", "title": username,
                              "sub": f"ID: {uid}", "badge": pp_str, "badge_highlight": bool(pp_str)})
            more = f"... 还有 {total - 15} 位好友" if total > 15 else None
            img_url = await self._render_list_card(f"👥 好友列表", items, subtitle=f"共 {total} 人", more=more)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                for i, friend in enumerate(friends, 1):
                    avatar_url, text = self._format_user_info(friend)
                    chain: list = []
                    if avatar_url:
                        try:
                            chain.append(Comp.Image.fromURL(avatar_url))
                        except Exception:
                            pass
                    chain.append(Comp.Plain(f"👥 【{i}/{total}】\n{text}"))
                    await event.send(MessageChain(chain))
                    if i < total:
                        await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"获取好友列表失败: {e}")
            await event.send(MessageChain([Comp.Plain(get_info("friend.error", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # chart
    # ================================================================

    @osu_group.command("chart", alias={"图表", "统计"})
    async def get_chart(self, event: AstrMessageEvent, mode: str = "osu", days: int = 30, type: str = "pp"):
        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        if type not in ("pp", "rank", "accuracy", "acc"):
            await event.send(MessageChain([Comp.Plain(get_info(
                "common.error_generic", operation="生成图表",
                error=f"无效的图表类型: {type}\n支持的类型: pp, rank, accuracy"))]))
            return
        if days < 1 or days > 365:
            await event.send(MessageChain([Comp.Plain(get_info(
                "common.error_generic", operation="生成图表",
                error="天数范围必须在 1-365 之间"))]))
            return

        try:
            validated_mode = validate_osu_mode(mode)
            track_mode = to_track_mode(validated_mode)

            to_date = datetime.datetime.now(datetime.timezone.utc)
            from_date = to_date - timedelta(days=days)
            from_str = from_date.strftime("%Y-%m-%d")
            to_str = to_date.strftime("%Y-%m-%d")

            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type=f"{type.upper()} 图表"))]))

            stats_history = await self.osutrack.get_stats_history(osu_id, track_mode, from_str, to_str)
            if not stats_history:
                await event.send(MessageChain([Comp.Plain(get_info(
                    "common.error_generic", operation="获取统计数据",
                    error=f"在过去 {days} 天内没有找到任何统计数据"))]))
                return

            user_info = await self.osu.get_own_data(platform_id, validated_mode)
            username = user_info.username

            if type == "pp":
                hiscores = await self.osutrack.get_hiscores(osu_id, track_mode, from_str, to_str)
                chart_buf = self._generate_pp_chart(stats_history, hiscores, username, validated_mode, days)
            elif type == "rank":
                chart_buf = self._generate_rank_chart(stats_history, username, validated_mode, days)
            else:
                chart_buf = self._generate_accuracy_chart(stats_history, username, validated_mode, days)

            await event.send(MessageChain([Comp.Image.fromBytes(chart_buf.read())]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="参数验证", error=str(e)))]))
        except Exception as e:
            logger.error(f"生成图表失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="生成图表", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # best / recent
    # ================================================================

    @osu_group.command("best", alias={"最佳", "bp"})
    async def get_best(self, event: AstrMessageEvent, mode: str = None, limit: int = 5):
        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        limit = max(1, min(limit, 20))
        try:
            validated_mode = validate_osu_mode(mode or "osu")
            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="最佳成绩"))]))
            scores = await self.osu.get_user_scores(
                platform_id, int(osu_id), "best",
                mode=validated_mode, limit=limit,
            )
            if not scores:
                await event.send(MessageChain([Comp.Plain(get_info("scores.empty", type="最佳成绩"))]))
                return

            # 尝试文转图
            img_url = await self._render_score_card(scores, "🏆 最佳成绩", str(osu_id))
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("scores.best_header", mode=validated_mode.upper(), count=len(scores))]
                for i, s in enumerate(scores, 1):
                    parts.append(self._format_score(s, index=i))
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("common.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"获取最佳成绩失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取最佳成绩", error=str(e)))]))
        event.stop_event()

    @osu_group.command("recent", alias={"最近", "rp"})
    async def get_recent(self, event: AstrMessageEvent, mode: str = None, limit: int = 5):
        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        limit = max(1, min(limit, 20))
        try:
            validated_mode = validate_osu_mode(mode or "osu")
            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="最近成绩"))]))
            scores = await self.osu.get_user_scores(
                platform_id, int(osu_id), "recent",
                mode=validated_mode, limit=limit, include_fails=1,
            )
            if not scores:
                await event.send(MessageChain([Comp.Plain(get_info("scores.empty", type="最近成绩"))]))
                return

            # 尝试文转图
            img_url = await self._render_score_card(scores, "🕐 最近游玩", str(osu_id))
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("scores.recent_header", mode=validated_mode.upper(), count=len(scores))]
                for i, s in enumerate(scores, 1):
                    parts.append(self._format_score(s, index=i))
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("common.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"获取最近成绩失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取最近成绩", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # scores / score
    # ================================================================

    @osu_group.command("scores", alias={"谱面排行"})
    async def get_beatmap_scores(self, event: AstrMessageEvent, beatmap_id: str, mode: str = None):
        if not beatmap_id or not beatmap_id.isdigit():
            await event.send(MessageChain([Comp.Plain(get_info("scores.scores_usage"))]))
            return

        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            validated_mode = validate_osu_mode(mode) if mode else None
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type=f"谱面 {beatmap_id} 排行"))]))
            result = await self.osu.get_beatmap_scores(
                platform_id, int(beatmap_id), mode=validated_mode,
            )
            if not result.scores:
                await event.send(MessageChain([Comp.Plain(
                    get_info("scores.empty", type=f"谱面 {beatmap_id} 排行"))]))
                return

            # 尝试文转图
            img_url = await self._render_score_card(result.scores[:10], f"🏅 谱面排行 #{beatmap_id}", f"共 {len(result.scores)} 条")
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("scores.beatmap_scores_header", id=beatmap_id, count=len(result.scores))]
                for i, s in enumerate(result.scores[:10], 1):
                    parts.append(self._format_score(s, index=i))
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("common.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"获取谱面排行失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取谱面排行", error=str(e)))]))
        event.stop_event()

    @osu_group.command("score", alias={"成绩"})
    async def get_user_beatmap_score(self, event: AstrMessageEvent, beatmap_id: str, mode: str = None):
        if not beatmap_id or not beatmap_id.isdigit():
            await event.send(MessageChain([Comp.Plain(get_info("scores.score_usage"))]))
            return

        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            validated_mode = validate_osu_mode(mode) if mode else None
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type=f"谱面 {beatmap_id} 个人成绩"))]))
            result = await self.osu.get_user_beatmap_score(
                platform_id, int(beatmap_id), int(osu_id), mode=validated_mode,
            )
            if not result.score:
                await event.send(MessageChain([Comp.Plain(
                    get_info("scores.empty", type=f"谱面 {beatmap_id} 个人成绩"))]))
                return

            # 尝试文转图
            s = result.score
            mods_str = ", ".join((m.get("acronym", "?") if isinstance(m, dict) else str(m)) for m in s.mods) if s.mods else ""
            sections = [
                {"type": "grid", "label": "成绩详情", "items": [
                    {"label": "PP", "value": f"{s.pp:.2f}" if s.pp is not None else "-", "color": "pp", "highlight": True},
                    {"label": "准确率", "value": f"{s.accuracy * 100:.2f}%", "color": "acc"},
                    {"label": "连击", "value": f"{s.max_combo:,}x", "color": "combo"},
                    {"label": "分数", "value": f"{s.total_score:,}", "color": "score"},
                ]},
            ]
            tags_list = [{"text": f"#{result.position}", "color": "pink"}]
            if mods_str:
                tags_list.append({"text": mods_str, "color": "blue"})
            img_url = await self._render_info_card(
                f"谱面 #{beatmap_id} 个人成绩", sections,
                icon="🎯", tags=tags_list, rank_badge=s.rank,
            )
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("scores.user_score_header", id=beatmap_id, position=result.position)]
                parts.append(self._format_score(result.score))
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("common.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"获取个人谱面成绩失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取个人谱面成绩", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # peak
    # ================================================================

    @osu_group.command("peak", alias={"巅峰", "历史最佳"})
    async def get_peak(self, event: AstrMessageEvent, mode: str = None):
        auth_ok, platform_id, osu_id = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            validated_mode = validate_osu_mode(mode or "osu")
            track_mode = to_track_mode(validated_mode)

            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="历史巅峰"))]))
            peak = await self.osutrack.get_peak(osu_id, track_mode)

            parts = [get_info("peak.header", mode=validated_mode.upper())]
            if peak.best_global_rank is not None:
                ts = peak.best_rank_timestamp or "-"
                parts.append(get_info("peak.best_rank", rank=f"{peak.best_global_rank:,}", time=ts))
            if peak.best_accuracy is not None:
                ts = peak.best_acc_timestamp or "-"
                parts.append(get_info("peak.best_accuracy", accuracy=f"{peak.best_accuracy:.2f}", time=ts))
            if len(parts) == 1:
                await event.send(MessageChain([Comp.Plain(get_info("scores.empty", type="历史巅峰"))]))
                return
            # 尝试文转图
            grid_items = []
            if peak.best_global_rank is not None:
                grid_items.append({"label": "最高排名", "value": f"#{peak.best_global_rank:,}", "color": "rank", "highlight": True,
                                   "sub": peak.best_rank_timestamp or ""})
            if peak.best_accuracy is not None:
                grid_items.append({"label": "最高准确率", "value": f"{peak.best_accuracy:.2f}%", "color": "acc", "highlight": True,
                                   "sub": peak.best_acc_timestamp or ""})
            img_url = await self._render_info_card(
                f"🏔️ 历史巅峰", [{"type": "grid", "items": grid_items}],
                subtitle=validated_mode.upper(), icon="🏔️",
            )
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("common.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"获取历史巅峰失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取历史巅峰", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # search
    # ================================================================

    @osu_group.group("search", alias={"搜索"})
    def search_group(self, event: AstrMessageEvent):
        pass

    @search_group.command("map", alias={"谱面"})
    async def search_map(self, event: AstrMessageEvent, query: str, num_per_page: int, page_num: int, flag: str = None):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        if not query:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.search_usage"))]))
            return
        if num_per_page <= 0 or num_per_page > 50:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.search_num_per_page_error"))]))
            return
        if page_num < 1:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.search_page_num_error"))]))
            return

        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="搜索"))]))
            search_results = await self.osu.search_beatmapsets(platform_id, query=query)
            await self._process_search_results(event, search_results.beatmapsets, num_per_page, page_num, "搜索", total_results=len(search_results))
        except Exception as e:
            logger.error(f"搜索谱面失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                f"❌ 搜索失败: {str(e)}\n请检查搜索参数，或稍后重试")]))
        event.stop_event()

    # ================================================================
    # ranking
    # ================================================================

    @osu_group.command("ranking", alias={"排行", "排名"})
    async def get_ranking(self, event: AstrMessageEvent, mode: str = "osu", type: str = "performance"):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            validated_mode = validate_osu_mode(mode)
            if type not in ("performance", "score", "charts", "country"):
                await event.send(MessageChain([Comp.Plain(
                    get_info("ranking.invalid_type"))]))
                return

            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type=f"{type} 排行榜"))]))
            data = await self.osu.get_ranking(platform_id, validated_mode, type)
            ranking_list = data.get("ranking", [])
            if not ranking_list:
                await event.send(MessageChain([Comp.Plain(
                    get_info("scores.empty", type="排行榜"))]))
                return

            # 尝试文转图
            columns = [{"label": "玩家"}, {"label": "PP", "right": True},
                       {"label": "准确率", "right": True}, {"label": "游玩次数", "right": True}]
            rows = []
            for i, entry in enumerate(ranking_list[:20], 1):
                user = entry.get("user", {})
                username = user.get("username", "?")
                pp = entry.get("pp", 0)
                accuracy = entry.get("hit_accuracy", entry.get("accuracy", 0))
                play_count = entry.get("play_count", 0)
                rows.append({"rank": i, "cells": [
                    {"value": username, "type": "name"},
                    {"value": f"{pp:.0f}" if pp else "-", "type": "pp", "right": True},
                    {"value": f"{accuracy:.2f}%" if accuracy else "-", "type": "acc", "right": True},
                    {"value": f"{play_count:,}", "type": "plays", "right": True},
                ]})
            img_url = await self._render_ranking_card(
                f"🏆 {type.upper()} 排行榜", columns, rows,
                subtitle=validated_mode.upper(),
            )
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("ranking.header",
                                  mode=validated_mode.upper(), type=type, count=len(ranking_list))]
                for i, entry in enumerate(ranking_list[:20], 1):
                    user = entry.get("user", {})
                    username = user.get("username", "?")
                    pp = entry.get("pp", 0)
                    accuracy = entry.get("hit_accuracy", entry.get("accuracy", 0))
                    play_count = entry.get("play_count", 0)
                    parts.append(get_info("ranking.entry",
                                          rank=i, username=username,
                                          pp=f"{pp:.0f}" if pp else "-",
                                          accuracy=f"{accuracy:.2f}" if accuracy else "-",
                                          play_count=f"{play_count:,}"))
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("common.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"获取排行榜失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取排行榜", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # match
    # ================================================================

    @osu_group.command("match", alias={"比赛"})
    async def get_match(self, event: AstrMessageEvent, match_id: str):
        if not match_id or not match_id.isdigit():
            await event.send(MessageChain([Comp.Plain(get_info("match.usage"))]))
            return

        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type=f"比赛 {match_id}"))]))
            data = await self.osu.get_match(platform_id, int(match_id))

            match_info = data.get("match", {})
            events = data.get("events", [])
            game_events = [e for e in events if e.get("detail", {}).get("type") == "other" and e.get("game")]

            # 尝试文转图
            tags = [{"text": f"ID: {match_info.get('id', match_id)}", "color": "blue"}]
            end_time = match_info.get("end_time")
            tags.append({"text": "进行中" if not end_time else "已结束", "color": "green" if not end_time else ""})
            sections = [
                {"type": "rows", "label": "比赛信息", "items": [
                    {"label": "开始时间", "value": match_info.get("start_time", "-")},
                    {"label": "结束时间", "value": end_time or "进行中"},
                    {"label": "对局数", "value": str(len(game_events))},
                ]},
            ]
            if game_events:
                game_items = []
                for ge in game_events[-5:]:
                    game = ge["game"]
                    beatmap = game.get("beatmap", {})
                    bm_name = beatmap.get("version", "?")
                    scores_list = game.get("scores", [])
                    mods = ", ".join(game.get("mods", [])) or "None"
                    game_items.append({"label": bm_name, "value": f"{len(scores_list)}人 | {mods}"})
                sections.append({"type": "rows", "label": "最近对局", "items": game_items})

            img_url = await self._render_info_card(
                match_info.get("name", "?"), sections, icon="⚔️", tags=tags,
            )
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("match.header",
                                  name=match_info.get("name", "?"),
                                  id=match_info.get("id", match_id),
                                  start_time=match_info.get("start_time", "-"),
                                  end_time=end_time or "进行中")]
                if game_events:
                    parts.append(get_info("match.games_header", count=len(game_events)))
                    for ge in game_events[-5:]:
                        game = ge["game"]
                        beatmap = game.get("beatmap", {})
                        bm_name = beatmap.get("version", "?")
                        bm_id = game.get("beatmap_id", "?")
                        scores_list = game.get("scores", [])
                        parts.append(get_info("match.game_entry",
                                              beatmap=bm_name, beatmap_id=bm_id,
                                              player_count=len(scores_list),
                                              mods=", ".join(game.get("mods", [])) or "None"))
                else:
                    parts.append("  暂无游戏记录")
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取比赛详情失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取比赛详情", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # mp (multiplayer rooms)
    # ================================================================

    @osu_group.command("mp", alias={"多人", "房间"})
    async def get_mp(self, event: AstrMessageEvent, room_id: str = None):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            if room_id and room_id.isdigit():
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.loading", type=f"房间 {room_id}"))]))
                data = await self.osu.get_room(platform_id, int(room_id))

                # 尝试文转图
                host = data.get("host", {})
                playlist = data.get("playlist", [])
                tags = [{"text": data.get("type", "?"), "color": "blue"},
                        {"text": "活跃" if data.get("active") else "已结束",
                         "color": "green" if data.get("active") else ""}]
                sections = [{"type": "rows", "label": "房间信息", "items": [
                    {"label": "ID", "value": str(data.get("id", room_id))},
                    {"label": "房主", "value": host.get("username", "?") if host else "-"},
                ]}]
                if playlist:
                    pl_items = [{"label": item.get("beatmap", {}).get("version", "?"),
                                 "value": f"ID: {item.get('beatmap_id', '?')}"} for item in playlist[:5]]
                    sections.append({"type": "rows", "label": f"曲目列表 ({len(playlist)})", "items": pl_items})
                img_url = await self._render_info_card(data.get("name", "?"), sections, icon="🎮", tags=tags)
                if img_url:
                    await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
                else:
                    parts = [get_info("mp.room_header",
                                      name=data.get("name", "?"),
                                      id=data.get("id", room_id),
                                      type=data.get("type", "?"),
                                      active=str(data.get("active", False)))]
                    if host:
                        parts.append(get_info("mp.room_host",
                                              username=host.get("username", "?")))
                    if playlist:
                        parts.append(get_info("mp.playlist_header", count=len(playlist)))
                        for item in playlist[:5]:
                            beatmap = item.get("beatmap", {})
                            parts.append(f"  • {beatmap.get('version', '?')} (ID: {item.get('beatmap_id', '?')})")
                    await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
            else:
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.loading", type="多人房间列表"))]))
                rooms = await self.osu.get_rooms(platform_id)

                if not rooms:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("scores.empty", type="多人房间"))]))
                    return

                # 尝试文转图
                items = []
                for i, room in enumerate(rooms[:10], 1):
                    active = room.get("active", False)
                    items.append({"index": i, "icon": "🎮", "title": room.get("name", "?"),
                                  "sub": f"ID: {room.get('id', '?')} | {room.get('type', '?')}",
                                  "badge": "活跃" if active else "关闭",
                                  "badge_highlight": active})
                img_url = await self._render_list_card("🎮 多人房间", items, subtitle=f"共 {len(rooms)} 个")
                if img_url:
                    await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
                else:
                    parts = [get_info("mp.list_header", count=len(rooms))]
                    for i, room in enumerate(rooms[:10], 1):
                        parts.append(get_info("mp.list_entry",
                                              rank=i,
                                              name=room.get("name", "?"),
                                              id=room.get("id", "?"),
                                              type=room.get("type", "?"),
                                              active=str(room.get("active", False))))
                    await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取多人房间失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取多人房间", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # news
    # ================================================================

    @osu_group.command("news", alias={"新闻"})
    async def get_news(self, event: AstrMessageEvent, news_id: str = None):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            if news_id:
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.loading", type="新闻文章"))]))
                key = "id" if news_id.isdigit() else None
                data = await self.osu.get_news_post(platform_id, news_id, key=key)

                # 尝试文转图
                content_html = data.get("content", "")
                preview = data.get("preview", "")
                slug = data.get("slug", "")
                link = f"https://osu.ppy.sh/home/news/{slug}" if slug else None
                img_url = await self._render_content_card(
                    data.get("title", "?"), content_html or preview[:800],
                    author=data.get("author"), date=data.get("published_at", "-")[:10],
                    link=link, truncated=not content_html and len(preview) > 800,
                    raw_html=bool(content_html),
                )
                if img_url:
                    await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
                else:
                    parts = [get_info("news.article_header",
                                      title=data.get("title", "?"),
                                      author=data.get("author", "?"),
                                      published_at=data.get("published_at", "-"))]
                    if preview:
                        parts.append(f"\n{preview[:500]}")
                        if len(preview) > 500:
                            parts.append("...")
                    if slug:
                        parts.append(f"\n🔗 https://osu.ppy.sh/home/news/{slug}")
                    await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
            else:
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.loading", type="新闻列表"))]))
                data = await self.osu.get_news_listing(platform_id, limit=10)
                posts = data.get("news_posts", [])

                if not posts:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("scores.empty", type="新闻"))]))
                    return

                # 尝试文转图
                items = []
                for i, post in enumerate(posts[:10], 1):
                    slug = post.get("slug", "")
                    news_id_str = slug or str(post.get("id", "?"))
                    items.append({"index": i, "icon": "📰", "title": post.get("title", "?"),
                                  "sub": f"{post.get('author', '?')} · {post.get('published_at', '-')[:10]}",
                                  "badge": news_id_str})
                img_url = await self._render_list_card("📰 osu! 新闻", items, subtitle=f"共 {len(posts)} 条")
                if img_url:
                    await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
                else:
                    parts = [get_info("news.list_header", count=len(posts))]
                    for i, post in enumerate(posts[:10], 1):
                        slug = post.get("slug", "")
                        news_id_str = slug or str(post.get("id", "?"))
                        parts.append(get_info("news.list_entry",
                                              rank=i,
                                              title=post.get("title", "?"),
                                              author=post.get("author", "?"),
                                              published_at=post.get("published_at", "-")[:10],
                                              news_id=news_id_str))
                    parts.append(get_info("news.list_footer"))
                    await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取新闻失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取新闻", error=str(e)))]))
        event.stop_event()

    @osu_group.command("news_subscribe", alias={"订阅新闻"})
    async def news_subscribe(self, event: AstrMessageEvent):
        session = event.unified_msg_origin
        if session in self._news_push_sessions:
            await event.send(MessageChain([Comp.Plain("当前会话已订阅 osu! 新闻推送。")]))
        else:
            self._news_push_sessions.append(session)
            self.config["news_push_sessions"] = self._news_push_sessions
            self.config.save_config()
            await event.send(MessageChain([Comp.Plain(
                f"✅ 已订阅 osu! 新闻推送！\n"
                f"当前推送模式: {self._news_push_mode}\n"
                f"{'⚠️ 注意：新闻推送功能未启用，请在配置中开启 news_push_enabled' if not self._news_push_enabled else ''}"
            )]))
        event.stop_event()

    @osu_group.command("news_unsubscribe", alias={"取消订阅新闻"})
    async def news_unsubscribe(self, event: AstrMessageEvent):
        session = event.unified_msg_origin
        if session in self._news_push_sessions:
            self._news_push_sessions.remove(session)
            self.config["news_push_sessions"] = self._news_push_sessions
            self.config.save_config()
            await event.send(MessageChain([Comp.Plain("✅ 已取消订阅 osu! 新闻推送。")]))
        else:
            await event.send(MessageChain([Comp.Plain("当前会话未订阅 osu! 新闻推送。")]))
        event.stop_event()

    # ================================================================
    # wiki
    # ================================================================

    @osu_group.command("wiki", alias={"百科"})
    async def get_wiki(self, event: AstrMessageEvent, path: str):
        if not path:
            await event.send(MessageChain([Comp.Plain(get_info("wiki.usage"))]))
            return

        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type="Wiki"))]))
            data = await self.osu.get_wiki_page(platform_id, "zh", path)

            title = data.get("title", path)
            markdown = data.get("markdown", "")
            # 将 markdown 转换为 HTML 用于渲染
            try:
                import markdown as md_lib
                content_html = md_lib.markdown(markdown, extensions=['tables', 'fenced_code'])
            except ImportError:
                content_html = ""
            # 简化 markdown 内容为纯文本预览（文本 fallback 用）
            import re
            plain = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', markdown)
            plain = re.sub(r'[#*_`>~]', '', plain)
            plain = re.sub(r'\n{3,}', '\n\n', plain).strip()

            parts = [get_info("wiki.header", title=title, path=path)]
            preview = plain[:1000]
            parts.append(preview)
            if len(plain) > 1000:
                parts.append(f"\n... (内容过长已截断)")
            parts.append(f"\n🔗 https://osu.ppy.sh/wiki/zh/{path}")
            # 尝试文转图
            link = f"https://osu.ppy.sh/wiki/zh/{path}"
            img_url = await self._render_content_card(
                title, content_html or preview, category="Wiki", link=link,
                truncated=not content_html and len(plain) > 1000,
                raw_html=bool(content_html),
            )
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取 Wiki 页面失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取 Wiki 页面", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # changelog
    # ================================================================

    @osu_group.command("changelog", alias={"更新日志"})
    async def get_changelog(self, event: AstrMessageEvent, stream: str = None):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type="更新日志"))]))
            data = await self.osu.get_changelog_listing(platform_id, stream=stream)
            builds = data.get("builds", [])

            if not builds:
                await event.send(MessageChain([Comp.Plain(
                    get_info("scores.empty", type="更新日志"))]))
                return

            parts = [get_info("changelog.header", count=len(builds))]
            items = []
            for idx, b in enumerate(builds[:10], 1):
                display_ver = b.get("display_version", b.get("version", "?"))
                stream_name = b.get("update_stream", {}).get("display_name", "?")
                created_at = (b.get("created_at") or "-")[:10]
                entries = b.get("changelog_entries", [])
                parts.append(get_info("changelog.build_entry",
                                      version=display_ver,
                                      stream=stream_name,
                                      date=created_at,
                                      entry_count=len(entries)))
                for entry in entries[:3]:
                    title = entry.get("title", "?")
                    parts.append(f"    • {title}")
                if len(entries) > 3:
                    parts.append(f"    ... 还有 {len(entries) - 3} 项更新")
                top_entry = entries[0].get("title", "") if entries else ""
                items.append({"index": idx, "icon": "🔄", "title": f"{stream_name} {display_ver}",
                              "sub": f"{created_at} · {len(entries)} 项更新" + (f" · {top_entry}" if top_entry else "")})
            # 尝试文转图
            img_url = await self._render_list_card("📋 更新日志", items, subtitle=f"共 {len(builds)} 条")
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取更新日志失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取更新日志", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # team
    # ================================================================

    @osu_group.command("team", alias={"团队"})
    async def get_team(self, event: AstrMessageEvent, team_id: str):
        if not team_id:
            await event.send(MessageChain([Comp.Plain(get_info("team.usage"))]))
            return

        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type=f"团队 {team_id}"))]))
            team_input = int(team_id) if team_id.isdigit() else team_id
            data = await self.osu.get_team(platform_id, team_input)

            name = data.get("name", "?")
            short_name = data.get("short_name", "")
            members = data.get("members", [])

            # 尝试文转图
            sections = []
            desc = data.get("description", "")
            if desc:
                sections.append({"type": "rows", "label": "简介", "items": [
                    {"label": "描述", "value": desc[:200]},
                ]})
            if members:
                member_names = [m.get("user", m).get("username", "?") for m in members[:15]]
                sections.append({"type": "members", "label": f"成员 ({len(members)})", "items": member_names})
            tags = []
            if short_name:
                tags.append({"text": short_name, "color": "pink"})
            tags.append({"text": f"{len(members)} 名成员", "color": "blue"})
            img_url = await self._render_info_card(name, sections, icon="👥", tags=tags)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("team.header",
                                  name=name,
                                  short_name=short_name,
                                  member_count=len(members))]
                if desc:
                    parts.append(f"📝 {desc[:200]}")
                if members:
                    parts.append(get_info("team.members_header"))
                    for m in members[:10]:
                        user = m.get("user", m)
                        parts.append(f"  • {user.get('username', '?')} (ID: {user.get('id', '?')})")
                    if len(members) > 10:
                        parts.append(f"  ... 还有 {len(members) - 10} 名成员")
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取团队信息失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取团队信息", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # packs
    # ================================================================

    @osu_group.command("packs", alias={"曲包"})
    async def get_packs(self, event: AstrMessageEvent, type: str = None):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type="谱面包列表"))]))
            data = await self.osu.get_beatmap_packs(platform_id, type=type)
            packs = data.get("beatmap_packs", [])

            if not packs:
                await event.send(MessageChain([Comp.Plain(
                    get_info("scores.empty", type="谱面包"))]))
                return

            # 尝试文转图
            items = []
            for i, pack in enumerate(packs[:15], 1):
                items.append({"index": i, "icon": "📦", "title": pack.get("name", "?"),
                              "sub": f"Tag: {pack.get('tag', '?')} · {pack.get('date', '-')}"})
            more = f"... 还有 {len(packs) - 15} 个谱面包" if len(packs) > 15 else None
            img_url = await self._render_list_card("📦 谱面包列表", items, subtitle=f"共 {len(packs)} 个", more=more)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("packs.header", count=len(packs))]
                for i, pack in enumerate(packs[:15], 1):
                    parts.append(get_info("packs.entry",
                                          rank=i,
                                          tag=pack.get("tag", "?"),
                                          name=pack.get("name", "?"),
                                          date=pack.get("date", "-")))
                if len(packs) > 15:
                    parts.append(f"... 还有 {len(packs) - 15} 个谱面包")
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取谱面包列表失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取谱面包列表", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # fav (favourites)
    # ================================================================

    @osu_group.command("fav", alias={"收藏"})
    async def get_favourites(self, event: AstrMessageEvent):
        auth_ok, platform_id, _ = await self._check_auth(event, need_identify=True)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type="收藏谱面"))]))
            data = await self.osu.get_beatmapset_favourites(platform_id)

            if not data:
                await event.send(MessageChain([Comp.Plain(
                    get_info("scores.empty", type="收藏谱面"))]))
                return

            # 尝试文转图
            items = []
            for i, bs in enumerate(data[:15], 1):
                title = bs.get("title", "?")
                artist = bs.get("artist", "?")
                bs_id = bs.get("id", "?")
                items.append({"index": i, "icon": "🎵", "title": f"{title} - {artist}",
                              "sub": f"ID: {bs_id}"})
            more = f"... 还有 {len(data) - 15} 个收藏" if len(data) > 15 else None
            img_url = await self._render_list_card("❤️ 收藏谱面", items, subtitle=f"共 {len(data)} 个", more=more)
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("fav.header", count=len(data))]
                for i, bs in enumerate(data[:15], 1):
                    title = bs.get("title", "?")
                    artist = bs.get("artist", "?")
                    bs_id = bs.get("id", "?")
                    parts.append(f"  {i}. 🎵 {title} - {artist} (ID: {bs_id})")
                if len(data) > 15:
                    parts.append(f"  ... 还有 {len(data) - 15} 个收藏")
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取收藏失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取收藏谱面", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # events
    # ================================================================

    @osu_group.command("events", alias={"事件"})
    async def get_events(self, event: AstrMessageEvent):
        auth_ok, platform_id, _ = await self._check_auth(event)
        if not auth_ok:
            return

        try:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type="事件流"))]))
            data = await self.osu.get_events(platform_id)
            events_list = data.get("events", [])

            if not events_list:
                await event.send(MessageChain([Comp.Plain(
                    get_info("scores.empty", type="事件"))]))
                return

            # 尝试文转图
            items = []
            for i, ev in enumerate(events_list[:15], 1):
                ev_type = ev.get("type", "?")
                created_at = (ev.get("created_at") or "-")[:16]
                user = ev.get("user", {})
                username = user.get("username", "") if user else ""
                title = ev_type
                if username:
                    title += f" - {username}"
                items.append({"index": i, "icon": "📌", "title": title, "sub": created_at})
            img_url = await self._render_list_card("📢 事件流", items, subtitle=f"共 {len(events_list)} 条")
            if img_url:
                await event.send(MessageChain([Comp.Image.fromURL(img_url)]))
            else:
                parts = [get_info("events.header", count=len(events_list))]
                for i, ev in enumerate(events_list[:15], 1):
                    ev_type = ev.get("type", "?")
                    created_at = (ev.get("created_at") or "-")[:16]
                    user = ev.get("user", {})
                    username = user.get("username", "") if user else ""
                    text = f"  {i}. [{created_at}] {ev_type}"
                    if username:
                        text += f" - {username}"
                    parts.append(text)
                await event.send(MessageChain([Comp.Plain("\n".join(parts))]))
        except Exception as e:
            logger.error(f"获取事件流失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取事件流", error=str(e)))]))
        event.stop_event()

    # ================================================================
    # LLM Tools
    # ================================================================

    @filter.llm_tool(name="query_osu_user")
    async def tool_query_user(self, event: AstrMessageEvent, username: str) -> MessageEventResult:
        '''查询 osu! 玩家信息。

        Args:
            username(string): osu! 玩家的用户名或数字 ID
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            processed: str | int = int(username) if username.isdigit() else username
            user_info = await self.osu.get_user(platform_id, processed)
            _, text = self._format_user_info(user_info)
            yield event.plain_result(text)
        except Exception as e:
            yield event.plain_result(f"查询玩家 {username} 失败: {e}")

    @filter.llm_tool(name="query_osu_beatmap")
    async def tool_query_beatmap(self, event: AstrMessageEvent, beatmap_id: str) -> MessageEventResult:
        '''查询 osu! 谱面信息。

        Args:
            beatmap_id(string): osu! 谱面的数字 ID
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            bm = await self.osu.get_beatmap(platform_id, int(beatmap_id))
            yield event.plain_result(self._format_beatmap_info(bm))
        except Exception as e:
            yield event.plain_result(f"查询谱面 {beatmap_id} 失败: {e}")

    @filter.llm_tool(name="query_osu_best_scores")
    async def tool_query_best(self, event: AstrMessageEvent, username: str, mode: str = "osu", limit: str = "5") -> MessageEventResult:
        '''查询 osu! 玩家的最佳 (BP) 成绩列表。

        Args:
            username(string): osu! 玩家的用户名或数字 ID
            mode(string): 游戏模式，可选 osu / taiko / fruits / mania，默认 osu
            limit(string): 返回数量，1-10，默认 5
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            processed: str | int = int(username) if username.isdigit() else username
            user_info = await self.osu.get_user(platform_id, processed, mode=mode)
            count = min(max(int(limit), 1), 10)
            scores = await self.osu.get_user_scores(platform_id, user_info.id, "best", mode=mode, limit=count)
            if not scores:
                yield event.plain_result(f"玩家 {user_info.username} 暂无最佳成绩记录。")
                return
            lines = [f"🏆 {user_info.username} 的最佳成绩 ({mode}):"]
            for i, s in enumerate(scores, 1):
                lines.append(self._format_score(s, index=i))
            yield event.plain_result("\n\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"查询最佳成绩失败: {e}")

    @filter.llm_tool(name="query_osu_recent_scores")
    async def tool_query_recent(self, event: AstrMessageEvent, username: str, mode: str = "osu", limit: str = "5") -> MessageEventResult:
        '''查询 osu! 玩家的最近游玩成绩（包含失败成绩）。

        Args:
            username(string): osu! 玩家的用户名或数字 ID
            mode(string): 游戏模式，可选 osu / taiko / fruits / mania，默认 osu
            limit(string): 返回数量，1-10，默认 5
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            processed: str | int = int(username) if username.isdigit() else username
            user_info = await self.osu.get_user(platform_id, processed, mode=mode)
            count = min(max(int(limit), 1), 10)
            scores = await self.osu.get_user_scores(platform_id, user_info.id, "recent", mode=mode, limit=count, include_fails=1)
            if not scores:
                yield event.plain_result(f"玩家 {user_info.username} 最近没有游玩记录。")
                return
            lines = [f"🕐 {user_info.username} 的最近游玩 ({mode}):"]
            for i, s in enumerate(scores, 1):
                lines.append(self._format_score(s, index=i))
            yield event.plain_result("\n\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"查询最近成绩失败: {e}")

    @filter.llm_tool(name="search_osu_beatmapsets")
    async def tool_search_beatmapsets(self, event: AstrMessageEvent, query: str) -> MessageEventResult:
        '''搜索 osu! 谱面集，返回最相关的前 5 个结果。

        Args:
            query(string): 搜索关键词（曲名、艺术家、谱师等）
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            result = await self.osu.search_beatmapsets(platform_id, query=query)
            beatmapsets = result.beatmapsets[:5] if result.beatmapsets else []
            if not beatmapsets:
                yield event.plain_result(f"未找到与「{query}」相关的谱面。")
                return
            lines = [f"🔍 搜索「{query}」的结果（共 {result.total} 个，显示前 {len(beatmapsets)} 个）:"]
            for bs in beatmapsets:
                _, text = self._format_beatmapset_info(bs, show_beatmaps=False)
                lines.append(text)
            yield event.plain_result("\n\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"搜索谱面失败: {e}")

    @filter.llm_tool(name="query_osu_user_score")
    async def tool_query_user_score(self, event: AstrMessageEvent, beatmap_id: str, username: str = "") -> MessageEventResult:
        '''查询某个玩家在指定谱面上的个人成绩和排名。如果不指定玩家，则查询调用者自己的成绩。

        Args:
            beatmap_id(string): 谱面的数字 ID
            username(string): osu! 玩家用户名或 ID，留空表示查询自己
        '''
        platform_id = event.get_sender_id()
        osu_id = self.link_mgr.get_osu_id(platform_id)
        if not osu_id or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            if username:
                processed: str | int = int(username) if username.isdigit() else username
                user_info = await self.osu.get_user(platform_id, processed)
                uid = user_info.id
                uname = user_info.username
            else:
                uid = int(osu_id)
                own = await self.osu.get_own_data(platform_id)
                uname = own.username
            result = await self.osu.get_user_beatmap_score(platform_id, int(beatmap_id), uid)
            score = result.score
            pos = result.position
            text = self._format_score(score)
            yield event.plain_result(f"🎯 {uname} 在谱面 {beatmap_id} 上的成绩（排名 #{pos}）:\n{text}")
        except Exception as e:
            yield event.plain_result(f"查询成绩失败: {e}")

    @filter.llm_tool(name="query_osu_ranking")
    async def tool_query_ranking(self, event: AstrMessageEvent, mode: str = "osu", type: str = "performance") -> MessageEventResult:
        '''查询 osu! 全球排行榜，返回前 10 名。

        Args:
            mode(string): 游戏模式，可选 osu / taiko / fruits / mania，默认 osu
            type(string): 排行类型，可选 performance / score，默认 performance
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            data = await self.osu.get_ranking(platform_id, mode, type)
            ranking_list = data.get("ranking", [])[:10]
            if not ranking_list:
                yield event.plain_result("排行榜数据为空。")
                return
            type_label = {"performance": "PP", "score": "Score"}.get(type, type)
            lines = [f"🏅 {mode.upper()} {type_label} 排行榜 Top 10:"]
            for i, entry in enumerate(ranking_list, 1):
                user = entry.get("user", {})
                name = user.get("username", "?")
                pp = entry.get("pp", 0)
                acc = entry.get("hit_accuracy", entry.get("accuracy", 0))
                lines.append(f"#{i} {name} | PP: {pp:,.0f} | 准确率: {acc:.2f}%")
            yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"查询排行榜失败: {e}")

    @filter.llm_tool(name="query_osu_wiki")
    async def tool_query_wiki(self, event: AstrMessageEvent, path: str, locale: str = "zh") -> MessageEventResult:
        '''查询 osu! Wiki 页面内容。可用于解释 osu! 相关术语、规则、玩法等。

        Args:
            path(string): Wiki 页面路径，例如 "Gameplay/Score" 或 "Beatmap"
            locale(string): 语言，默认 zh（中文），可选 en（英文）等
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            import re as _re
            data = await self.osu.get_wiki_page(platform_id, locale, path)
            title = data.get("title", path)
            markdown = data.get("markdown", "")
            # Strip markdown formatting for plain text
            plain = _re.sub(r'!\[.*?\]\(.*?\)', '', markdown)
            plain = _re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', plain)
            plain = _re.sub(r'[#*_`~>]', '', plain)
            plain = _re.sub(r'\n{3,}', '\n\n', plain).strip()
            if len(plain) > 1500:
                plain = plain[:1500] + "\n\n...（内容过长已截断）"
            yield event.plain_result(f"📖 Wiki: {title}\n\n{plain}")
        except Exception as e:
            yield event.plain_result(f"查询 Wiki 失败: {e}")

    @filter.llm_tool(name="query_osu_news")
    async def tool_query_news(self, event: AstrMessageEvent, news_id: str = "") -> MessageEventResult:
        '''查询 osu! 新闻。不传参返回最新新闻列表；传入文章 ID 或 slug 返回文章详情。

        Args:
            news_id(string): 新闻文章的数字 ID 或 slug（可选，为空则返回列表）
        '''
        platform_id = event.get_sender_id()
        if not self.link_mgr.get_osu_id(platform_id) or not self.osu.has_valid_token(platform_id):
            yield event.plain_result("用户尚未绑定 osu! 账号或授权已过期，请先使用 /osu link 绑定。")
            return
        try:
            if news_id:
                key = "id" if news_id.isdigit() else None
                data = await self.osu.get_news_post(platform_id, news_id, key=key)
                title = data.get("title", "?")
                preview = data.get("preview", "")
                author = data.get("author", "?")
                date = data.get("published_at", "-")[:10]
                slug = data.get("slug", "")
                text = f"📰 {title}\n✍️ {author} | 📅 {date}\n\n{preview}"
                if slug:
                    text += f"\n\n🔗 https://osu.ppy.sh/home/news/{slug}"
                yield event.plain_result(text)
            else:
                data = await self.osu.get_news_listing(platform_id, limit=10)
                posts = data.get("news_posts", [])
                if not posts:
                    yield event.plain_result("暂无新闻。")
                    return
                lines = ["📰 osu! 最新新闻:"]
                for i, post in enumerate(posts[:10], 1):
                    slug = post.get("slug", "")
                    nid = slug or str(post.get("id", "?"))
                    lines.append(f"{i}. {post.get('title', '?')} ({post.get('published_at', '-')[:10]}) [ID: {nid}]")
                lines.append("\n💡 可通过 ID 或 slug 查看详情")
                yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"查询新闻失败: {e}")

    # ================================================================
    # private helpers
    # ================================================================

    async def _process_search_results(self, event: AstrMessageEvent, results: list,
                                      num_per_page: int, page_num: int,
                                      search_type: str, total_results: int = 0):
        if not results:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.search_no_results"))]))
            return

        total_pages = (total_results + num_per_page - 1) // num_per_page if total_results > 0 else 1
        await event.send(MessageChain([Comp.Plain(get_info(
            "beatmap.search_overview", type=search_type, count=len(results),
            total=total_results, page=page_num, total_pages=total_pages))]))

        for i, bs in enumerate(results, 1):
            cover_url, text = self._format_beatmapset_info(bs, show_beatmaps=False)
            prefix = f"【{i + (page_num - 1) * num_per_page}/{total_results}】\n" if total_results else f"【{i}】\n"
            chain: list = []
            if cover_url:
                try:
                    chain.append(Comp.Image.fromURL(cover_url))
                except Exception:
                    pass
            chain.append(Comp.Plain(prefix + text))
            await event.send(MessageChain(chain))
            if i < len(results):
                await asyncio.sleep(0.5)

    async def _check_auth(
        self,
        event: AstrMessageEvent,
        *,
        need_identify: bool = False,
        need_friends: bool = False,
    ) -> tuple[bool, str, str]:
        platform_id = event.get_sender_id()

        osu_id = self.link_mgr.get_osu_id(platform_id)
        if not osu_id:
            await event.send(MessageChain([Comp.Plain(get_info("auth_check.not_linked"))]))
            return False, platform_id, ""

        if not self.osu.has_valid_token(platform_id):
            await event.send(MessageChain([Comp.Plain(get_info("auth_check.expired"))]))
            return False, platform_id, osu_id

        missing: list[str] = []
        if need_identify and not self.osu.has_scope(platform_id, "identify"):
            missing.append("identify")
        if need_friends and not self.osu.has_scope(platform_id, "friends.read"):
            missing.append("friends.read")

        if missing:
            await event.send(MessageChain([Comp.Plain(
                get_info("auth_check.insufficient_scope", scopes=", ".join(missing)))]))
            return False, platform_id, osu_id

        return True, platform_id, osu_id

    # --------------------------------------------------
    # HTML rendering helpers
    # --------------------------------------------------

    async def _render_user_card(self, user_info) -> str | None:
        """Render a user profile card as image URL. Returns None on failure."""
        tmpl = self._templates.get("user_card")
        if not tmpl or not self._use_image_output:
            return None
        s = user_info.statistics
        grades = None
        if s:
            grades = {
                "ssh": s.grade_counts_ssh,
                "ss": s.grade_counts_ss,
                "sh": s.grade_counts_sh,
                "s": s.grade_counts_s,
                "a": s.grade_counts_a,
            }
            acc = None
            if s.hit_accuracy is not None:
                acc = f"{s.hit_accuracy:.2f}"
            elif s.accuracy is not None:
                acc = f"{s.accuracy * 100:.2f}"
        data = {
            "username": user_info.username,
            "user_id": user_info.id,
            "avatar_url": user_info.avatar_url or "",
            "country_code": user_info.country_code or "",
            "is_online": getattr(user_info, "is_online", False),
            "is_supporter": getattr(user_info, "is_supporter", False),
            "pp": f"{s.pp:,.2f}" if s and s.pp is not None else None,
            "global_rank": f"{s.global_rank:,}" if s and s.global_rank is not None else None,
            "country_rank": f"{s.country_rank:,}" if s and s.country_rank is not None else None,
            "accuracy": acc if s else None,
            "play_count": f"{s.play_count:,}" if s and s.play_count is not None else None,
            "max_combo": f"{s.maximum_combo:,}" if s and s.maximum_combo is not None else None,
            "ranked_score": f"{s.ranked_score:,}" if s and s.ranked_score is not None else None,
            "total_score": f"{s.total_score:,}" if s and s.total_score is not None else None,
            "grades": grades,
        }
        try:
            return await self.html_render(tmpl, data, options={"omit_background": True})
        except Exception as e:
            logger.debug(f"HTML 渲染用户卡片失败: {e}")
            return None

    async def _render_score_card(self, scores: list, title: str, player_name: str) -> str | None:
        """Render a score list card as image URL. Returns None on failure."""
        tmpl = self._templates.get("score_card")
        if not tmpl or not self._use_image_output:
            return None
        score_data = []
        for s in scores:
            mods_str = ", ".join((m.get("acronym", "?") if isinstance(m, dict) else str(m)) for m in s.mods) if s.mods else ""
            score_data.append({
                "beatmap_id": s.beatmap_id,
                "rank": s.rank,
                "pp": f"{s.pp:.2f}" if s.pp is not None else None,
                "accuracy": f"{s.accuracy * 100:.2f}",
                "combo": f"{s.max_combo:,}",
                "total_score": f"{s.total_score:,}",
                "mods": mods_str,
                "ended_at": s.ended_at or "",
            })
        data = {"title": title, "player_name": player_name, "scores": score_data}
        try:
            return await self.html_render(tmpl, data, options={"omit_background": True})
        except Exception as e:
            logger.debug(f"HTML 渲染成绩卡片失败: {e}")
            return None

    async def _render_beatmap_card(self, bm=None, bs=None) -> str | None:
        """Render a beatmap/beatmapset card as image URL. Returns None on failure."""
        tmpl = self._templates.get("beatmap_card")
        if not tmpl or not self._use_image_output:
            return None
        data: dict = {}
        if bs:
            cover_url = None
            if hasattr(bs, "covers") and bs.covers:
                cover_url = bs.covers.cover or bs.covers.card
            data.update({
                "title": bs.title,
                "artist": getattr(bs, "artist", None),
                "creator": getattr(bs, "creator", None),
                "beatmap_id": bs.id,
                "beatmapset_id": None,
                "cover_url": cover_url,
                "status": getattr(bs, "status", None),
                "mode": None,
                "play_count": f"{bs.play_count:,}" if hasattr(bs, "play_count") and bs.play_count is not None else None,
                "favourite_count": f"{bs.favourite_count:,}" if hasattr(bs, "favourite_count") and bs.favourite_count is not None else None,
                "difficulty_rating": None,
                "bpm": None,
                "length": None,
                "ar": None, "cs": None, "hp": None,
                "pass_count": None,
                "beatmaps": [{"version": b.version, "stars": f"{b.difficulty_rating:.2f}"} for b in bs.beatmaps[:10]] if hasattr(bs, "beatmaps") and bs.beatmaps else None,
            })
        if bm:
            length_str = None
            if bm.total_length is not None:
                m, s = divmod(bm.total_length, 60)
                length_str = f"{m}:{s:02d}"
            data.update({
                "title": data.get("title") or bm.version,
                "beatmap_id": bm.id,
                "beatmapset_id": bm.beatmapset_id,
                "mode": bm.mode,
                "status": data.get("status") or bm.status,
                "difficulty_rating": f"{bm.difficulty_rating:.2f}" if bm.difficulty_rating else None,
                "bpm": bm.bpm,
                "length": length_str,
                "ar": bm.ar, "cs": bm.cs, "hp": bm.drain,
                "pass_count": f"{bm.passcount:,}" if bm.passcount else None,
            })
        try:
            return await self.html_render(tmpl, data, options={"omit_background": True})
        except Exception as e:
            logger.debug(f"HTML 渲染谱面卡片失败: {e}")
            return None

    async def _render_list_card(self, title: str, items: list[dict], subtitle: str = None, more: str = None) -> str | None:
        """Render a generic list card. Each item: {index, title, sub?, icon?, badge?, badge_highlight?}."""
        tmpl = self._templates.get("list_card")
        if not tmpl or not self._use_image_output:
            return None
        data = {"title": title, "subtitle": subtitle, "items": items, "more": more}
        try:
            return await self.html_render(tmpl, data, options={"omit_background": True})
        except Exception as e:
            logger.debug(f"HTML 渲染列表卡片失败: {e}")
            return None

    async def _render_ranking_card(self, title: str, columns: list[dict], rows: list[dict], subtitle: str = None) -> str | None:
        """Render a ranking/leaderboard card. columns: [{label, right?}], rows: [{rank, cells: [{value, type?, right?, mods?}]}]."""
        tmpl = self._templates.get("ranking_card")
        if not tmpl or not self._use_image_output:
            return None
        data = {"title": title, "subtitle": subtitle, "columns": columns, "rows": rows}
        try:
            return await self.html_render(tmpl, data, options={"omit_background": True})
        except Exception as e:
            logger.debug(f"HTML 渲染排行卡片失败: {e}")
            return None

    async def _render_info_card(self, title: str, sections: list[dict],
                                subtitle: str = None, icon: str = None,
                                tags: list[dict] = None, rank_badge: str = None) -> str | None:
        """Render a structured info card. sections: [{type: 'grid'|'rows'|'members', label?, items, cols_class?}]."""
        tmpl = self._templates.get("info_card")
        if not tmpl or not self._use_image_output:
            return None
        data = {"title": title, "subtitle": subtitle, "icon": icon,
                "tags": tags, "rank_badge": rank_badge, "sections": sections}
        try:
            return await self.html_render(tmpl, data, options={"omit_background": True})
        except Exception as e:
            logger.debug(f"HTML 渲染信息卡片失败: {e}")
            return None

    async def _render_content_card(self, title: str, content: str,
                                   author: str = None, date: str = None,
                                   category: str = None, link: str = None,
                                   truncated: bool = False,
                                   raw_html: bool = False) -> str | None:
        """Render a long-form content card. If raw_html=True, content is inserted as-is."""
        tmpl = self._templates.get("content_card")
        if not tmpl or not self._use_image_output:
            return None
        data = {"title": title, "content": content, "author": author,
                "date": date, "category": category, "link": link,
                "truncated": truncated, "raw_html": raw_html}
        try:
            return await self.html_render(tmpl, data, options={"omit_background": True})
        except Exception as e:
            logger.debug(f"HTML 渲染内容卡片失败: {e}")
            return None

    # --------------------------------------------------
    # Formatting
    # --------------------------------------------------

    def _format_user_info(self, user_info, is_self: bool = False) -> tuple[str, str]:
        avatar_url = user_info.avatar_url
        parts: list[str] = []
        parts.append(get_info("user.format.username", username=user_info.username))
        parts.append(get_info("user.format.user_id", id=user_info.id))

        if user_info.country_code:
            parts.append(get_info("user.format.country", country_code=user_info.country_code))

        if user_info.statistics:
            s = user_info.statistics
            parts.append(get_info("user.format.statistics_header"))
            if s.pp is not None:
                parts.append(get_info("user.format.pp", pp=f"{s.pp:.2f}"))
            if s.global_rank is not None:
                parts.append(get_info("user.format.global_rank", rank=f"{s.global_rank:,}"))
            if s.country_rank is not None:
                parts.append(get_info("user.format.country_rank", rank=f"{s.country_rank:,}"))
            if s.hit_accuracy is not None or s.accuracy is not None:
                acc = s.hit_accuracy if s.hit_accuracy is not None else s.accuracy * 100
                parts.append(get_info("user.format.accuracy", accuracy=f"{acc:.2f}"))
            if s.play_count is not None:
                parts.append(get_info("user.format.play_count", count=f"{s.play_count:,}"))
            if s.ranked_score is not None:
                parts.append(get_info("user.format.ranked_score", score=f"{s.ranked_score:,}"))
            if s.total_score is not None:
                parts.append(get_info("user.format.total_score", score=f"{s.total_score:,}"))
            if s.maximum_combo is not None:
                parts.append(get_info("user.format.max_combo", combo=f"{s.maximum_combo:,}"))

        if user_info.is_online:
            parts.append(get_info("user.format.status_online"))
        else:
            parts.append(get_info("user.format.status_offline"))

        if user_info.is_supporter:
            parts.append(get_info("user.format.supporter"))

        return avatar_url, "\n".join(parts)

    def _format_beatmap_info(self, bm) -> str:
        parts: list[str] = []
        parts.append(get_info("beatmap.format.version", version=bm.version))
        parts.append(get_info("beatmap.format.beatmap_id", id=bm.id))
        parts.append(get_info("beatmap.format.beatmapset_id", beatmapset_id=bm.beatmapset_id))
        parts.append(get_info("beatmap.format.difficulty", rating=f"{bm.difficulty_rating:.2f}"))
        parts.append(get_info("beatmap.format.mode", mode=bm.mode))
        parts.append(get_info("beatmap.format.status", status=bm.status))

        if bm.bpm is not None:
            parts.append(get_info("beatmap.format.bpm", bpm=bm.bpm))
        if bm.ar is not None:
            parts.append(get_info("beatmap.format.ar", ar=bm.ar))
        if bm.cs is not None:
            parts.append(get_info("beatmap.format.cs", cs=bm.cs))
        if bm.drain is not None:
            parts.append(get_info("beatmap.format.hp", hp=bm.drain))

        if bm.count_circles is not None or bm.count_sliders is not None:
            parts.append(get_info("beatmap.format.objects_header"))
            if bm.count_circles is not None:
                parts.append(get_info("beatmap.format.circles", count=bm.count_circles))
            if bm.count_sliders is not None:
                parts.append(get_info("beatmap.format.sliders", count=bm.count_sliders))
            if bm.count_spinners is not None:
                parts.append(get_info("beatmap.format.spinners", count=bm.count_spinners))

        if bm.total_length is not None:
            m, s = divmod(bm.total_length, 60)
            parts.append(get_info("beatmap.format.duration", time=f"{m}:{s:02d}"))
        if bm.playcount is not None:
            parts.append(get_info("beatmap.format.playcount", count=f"{bm.playcount:,}"))
        if bm.passcount is not None:
            parts.append(get_info("beatmap.format.passcount", count=f"{bm.passcount:,}"))

        return "\n".join(parts)

    def _format_beatmapset_info(self, bs, show_beatmaps: bool = True) -> tuple[str, str]:
        cover_url = None
        if hasattr(bs, "covers") and bs.covers:
            cover_url = bs.covers.card or bs.covers.cover
        elif hasattr(bs, "card_url"):
            cover_url = bs.card_url

        parts: list[str] = []
        parts.append(get_info("beatmap.mapset_format.title", title=bs.title))
        if hasattr(bs, "artist"):
            parts.append(get_info("beatmap.mapset_format.artist", artist=bs.artist))
        if hasattr(bs, "creator"):
            parts.append(get_info("beatmap.mapset_format.creator", creator=bs.creator))
        parts.append(get_info("beatmap.mapset_format.id", id=bs.id))
        if hasattr(bs, "status"):
            parts.append(get_info("beatmap.mapset_format.status", status=bs.status))
        if hasattr(bs, "play_count") and bs.play_count is not None:
            parts.append(get_info("beatmap.mapset_format.play_count", count=f"{bs.play_count:,}"))
        if hasattr(bs, "favourite_count") and bs.favourite_count is not None:
            parts.append(get_info("beatmap.mapset_format.favourite_count", count=f"{bs.favourite_count:,}"))

        if show_beatmaps and hasattr(bs, "beatmaps") and bs.beatmaps:
            parts.append(get_info("beatmap.mapset_format.beatmaps_header", total=len(bs.beatmaps)))
            for b in bs.beatmaps[:5]:
                parts.append(get_info("beatmap.mapset_format.beatmap_item",
                                      version=b.version, rating=f"{b.difficulty_rating:.2f}"))
            if len(bs.beatmaps) > 5:
                parts.append(get_info("beatmap.mapset_format.beatmaps_more",
                                      remaining=len(bs.beatmaps) - 5))

        return cover_url, "\n".join(parts)

    def _format_score(self, score, index: int = None) -> str:
        """Format a single Score object into a readable string."""
        mods_str = ", ".join((m.get("acronym", "?") if isinstance(m, dict) else str(m)) for m in score.mods) if score.mods else "None"
        prefix = f"#{index} " if index else ""
        parts: list[str] = []
        parts.append(get_info("scores.format.header", prefix=prefix, beatmap_id=score.beatmap_id, rank=score.rank))
        parts.append(get_info("scores.format.pp", pp=f"{score.pp:.2f}" if score.pp is not None else "-"))
        parts.append(get_info("scores.format.accuracy", accuracy=f"{score.accuracy * 100:.2f}"))
        parts.append(get_info("scores.format.combo", combo=f"{score.max_combo:,}"))
        parts.append(get_info("scores.format.mods", mods=mods_str))
        parts.append(get_info("scores.format.score", score=f"{score.total_score:,}"))
        if score.ended_at:
            parts.append(get_info("scores.format.time", time=score.ended_at))
        return "\n".join(parts)

    # --------------------------------------------------
    # Chart generation
    # --------------------------------------------------

    _RANK_COLORS = {
        "XH": "#FFD700", "X": "#C0C0C0", "SH": "#FFD700", "S": "#C0C0C0",
        "A": "#00FF00", "B": "#4169E1", "C": "#FF00FF", "D": "#FF0000", "F": "#808080",
    }
    _RANK_MARKERS = {
        "XH": "*", "X": "*", "SH": "D", "S": "D",
        "A": "o", "B": "s", "C": "^", "D": "v", "F": "x",
    }

    def _generate_pp_chart(self, stats: List[StatsUpdate], hiscores: List[RecordedScore],
                           username: str, mode: str, days: int) -> BytesIO:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        fig.suptitle(f"{username} - {mode.upper()} Mode PP Statistics (Last {days} Days)",
                     fontsize=16, fontweight="bold")

        if stats:
            ts = [datetime.datetime.fromisoformat(s.timestamp.replace("Z", "+00:00")) for s in stats]
            pp = [s.pp_raw for s in stats]
            ax1.plot(ts, pp, color="#FF66AA", linewidth=2, marker="o", markersize=4, label="PP")
            ax1.set_xlabel("Date"); ax1.set_ylabel("PP")
            ax1.set_title("PP Over Time", fontsize=14, fontweight="bold")
            ax1.grid(True, alpha=0.3); ax1.legend()
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            ax1.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

        if hiscores:
            by_rank: dict[str, dict] = {}
            for sc in hiscores:
                entry = by_rank.setdefault(sc.rank, {"t": [], "p": []})
                entry["t"].append(datetime.datetime.fromisoformat(sc.score_time.replace("Z", "+00:00")))
                entry["p"].append(sc.pp)
            for rank, d in by_rank.items():
                ax2.scatter(d["t"], d["p"], c=self._RANK_COLORS.get(rank.upper(), "#808080"),
                            marker=self._RANK_MARKERS.get(rank.upper(), "o"),
                            s=100, alpha=0.6, label=f"Rank {rank}", edgecolors="black", linewidths=0.5)
            ax2.set_xlabel("Date"); ax2.set_ylabel("PP")
            ax2.set_title("Score Performance (PP by Rank)", fontsize=14, fontweight="bold")
            ax2.grid(True, alpha=0.3); ax2.legend(loc="upper left", fontsize=8, ncol=2)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")

        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0); plt.close(fig)
        return buf

    def _generate_rank_chart(self, stats: List[StatsUpdate],
                             username: str, mode: str, days: int) -> BytesIO:
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.suptitle(f"{username} - {mode.upper()} Mode Rank Statistics (Last {days} Days)",
                     fontsize=16, fontweight="bold")
        if stats:
            ts = [datetime.datetime.fromisoformat(s.timestamp.replace("Z", "+00:00")) for s in stats]
            ranks = [s.pp_rank for s in stats]
            ax.plot(ts, ranks, color="#66B2FF", linewidth=2, marker="o", markersize=4, label="Global Rank")
            ax.set_xlabel("Date"); ax.set_ylabel("Rank")
            ax.set_title("Global Rank Over Time", fontsize=14, fontweight="bold")
            ax.grid(True, alpha=0.3); ax.legend()
            ax.invert_yaxis()
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0); plt.close(fig)
        return buf

    def _generate_accuracy_chart(self, stats: List[StatsUpdate],
                                 username: str, mode: str, days: int) -> BytesIO:
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.suptitle(f"{username} - {mode.upper()} Mode Accuracy Statistics (Last {days} Days)",
                     fontsize=16, fontweight="bold")
        if stats:
            ts = [datetime.datetime.fromisoformat(s.timestamp.replace("Z", "+00:00")) for s in stats]
            accs = [s.accuracy for s in stats]
            ax.plot(ts, accs, color="#FFB366", linewidth=2, marker="o", markersize=4, label="Accuracy")
            ax.set_xlabel("Date"); ax.set_ylabel("Accuracy (%)")
            ax.set_title("Accuracy Over Time", fontsize=14, fontweight="bold")
            ax.grid(True, alpha=0.3); ax.legend()
            if accs:
                pad = (max(accs) - min(accs)) * 0.1 or 1
                ax.set_ylim(min(accs) - pad, max(accs) + pad)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0); plt.close(fig)
        return buf

    # --------------------------------------------------

    async def terminate(self):
        if self._news_poll_task and not self._news_poll_task.done():
            self._news_poll_task.cancel()
            try:
                await self._news_poll_task
            except asyncio.CancelledError:
                pass
        if self._news_cron_job_id:
            try:
                await self.context.cron_manager.delete_job(self._news_cron_job_id)
            except Exception:
                pass
        if self._news_client:
            await self._news_client.close()
        await self.osu.close()
        await self.osutrack.close()
        await self.oauth.close()
        return await super().terminate()