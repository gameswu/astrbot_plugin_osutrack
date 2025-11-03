from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.util import session_waiter, SessionController
import astrbot.api.message_components as Comp

import urllib.parse
import asyncio
import datetime
from datetime import timedelta
from io import BytesIO
from typing import List, Tuple

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

from .utils import load_help_data, get_info
from .client.oauth_client import OsuOAuthClient
from .client.link_account import LinkAccountManager
from .client.token_manager import TokenManager
from .client.osu_client import OsuClient
from .client.osutrack_client import OsuTrackClient
from .osuapi.enumtype import Scopes, OsuModes
from .osuapi.trans import convert_osu_mode_to_track_mode, validate_osu_mode
from .osutrackapi.enums import GameMode
from .osutrackapi import StatsUpdate, RecordedScore

@register("osu","gameswu","基于osu!track与osu!api的osu!插件","0.2.2","https://github.com/gameswu/astrbot_plugin_osutrack")
class OsuTrackPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.link_account_manager = LinkAccountManager()
        self.token_manager = TokenManager()
        self.osu_client = OsuClient(self.token_manager)
        self.osu_track_client = OsuTrackClient()
        
        # 从配置获取 OAuth 设置
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret") 
        self.redirect_uri = config.get("redirect_uri", "http://localhost:7210/")
        
        # 加载帮助信息
        self.help_data = load_help_data()

    async def initialize(self):
        pass

    @filter.command_group("osu")
    async def osu(self, event: AstrMessageEvent):
        pass

    @osu.command("help") #@audit-ok
    async def help_command(self, event: AstrMessageEvent, command: str = None):
        """
        显示 OSU 插件帮助信息
        """
        if not self.help_data:
            await event.send(MessageChain([Comp.Plain("❌ 帮助信息加载失败，请联系管理员。")]))
            return

        if command:
            # 获取特定命令的帮助
            command_key = command.upper()
            help_text = self.help_data.get('commands', {}).get(command_key)
            if help_text:
                # 添加标题
                final_text = f"OSU! 插件帮助 - /osu {command.lower()}\n\n{help_text}"
            else:
                final_text = f"❌ 未找到命令 '{command}' 的帮助信息。\n\n"
                final_text += self.help_data.get('general', '帮助信息不可用。')
        else:
            # 获取通用帮助
            final_text = self.help_data.get('general', '帮助信息不可用。')
        
        await event.send(MessageChain([Comp.Plain(final_text)]))

    @osu.command("link") #@audit-ok
    async def link_account(self, event: AstrMessageEvent):
        """
        关联 OSU 账号和平台 ID
        """
        platform_id = event.get_sender_id()
        
        # 检查是否已经关联
        existing_osu_id = self.link_account_manager.get_osu_id_by_platform(platform_id)
        if existing_osu_id:
            await event.send(MessageChain([Comp.Plain(
                get_info("link.already_linked", osu_id=existing_osu_id)
            )]))
            return
        
        # 检查配置
        if not self.client_id or not self.client_secret:
            await event.send(MessageChain([Comp.Plain(get_info("link.config_incomplete"))]))
            return
        
        try:
            # 创建 OAuth 客户端
            oauth_client = OsuOAuthClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri
            )
            
            # 生成授权 URL
            state = f"{platform_id}_{int(asyncio.get_event_loop().time())}"
            auth_url = oauth_client.get_authorization_url(state)
            
            # 发送授权链接
            await event.send(MessageChain([Comp.Plain(
                get_info("link.auth_flow", auth_url=auth_url)
            )]))
            
            # 等待用户输入授权回调 URL
            @session_waiter(timeout=300)  # 5分钟超时
            async def handle_auth_callback(controller: SessionController, event: AstrMessageEvent):
                try:
                    callback_url = event.message_str.strip()
                    
                    # 验证并解析回调 URL
                    if "code=" not in callback_url:
                        await event.send(MessageChain([Comp.Plain(get_info("callback.invalid_url"))]))
                        controller.keep(60)  # 继续等待 60 秒
                        return
                    
                    # 提取授权码
                    parsed_url = urllib.parse.urlparse(callback_url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    
                    auth_code = query_params.get('code', [None])[0]
                    callback_state = query_params.get('state', [None])[0]
                    
                    if not auth_code:
                        await event.send(MessageChain([Comp.Plain(get_info("callback.no_code"))]))
                        controller.keep(60)
                        return
                    
                    # 验证 state 参数（可选的安全检查）
                    if callback_state and not callback_state.startswith(platform_id):
                        await event.send(MessageChain([Comp.Plain(get_info("callback.state_mismatch"))]))
                        controller.stop()
                        return
                    
                    # 显示处理中状态
                    await event.send(MessageChain([Comp.Plain(get_info("common.processing"))]))
                    
                    # 交换授权码获取访问令牌
                    token_data = await oauth_client.exchange_code_for_token(auth_code)
                    
                    # 保存 token
                    oauth_client.save_token(platform_id, token_data)
                    
                    # 获取用户信息
                    user_info = await oauth_client.get_user_info(platform_id)
                    if not user_info:
                        await event.send(MessageChain([Comp.Plain(get_info("callback.get_user_failed"))]))
                        controller.stop()
                        return
                    
                    osu_user_id = user_info["id"]
                    username = user_info["username"]
                    
                    # 关联账号
                    success = self.link_account_manager.link_account(osu_user_id, platform_id)
                    if success:
                        await event.send(MessageChain([Comp.Plain(
                            get_info("link.success", username=username, osu_user_id=osu_user_id, platform_id=platform_id)
                        )]))
                        logger.info(f"成功关联 OSU 账号: {username}({osu_user_id}) <-> {platform_id}")
                    else:
                        # 关联失败，清理 token
                        oauth_client.remove_token(platform_id)
                        await event.send(MessageChain([Comp.Plain(
                            get_info("callback.link_failed", platform_id=platform_id)
                        )]))
                    
                    controller.stop()
                    
                except Exception as e:
                    logger.error(f"处理 OSU 授权回调失败: {e}")
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="授权", error=str(e))
                    )]))
                    controller.stop()
            
            # 开始等待用户输入
            try:
                await handle_auth_callback(event)
            except TimeoutError:
                await event.send(MessageChain([Comp.Plain(get_info("callback.timeout"))]))
            
        except Exception as e:
            logger.error(f"OSU 账号关联过程中发生错误: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="关联", error=str(e))
            )]))

    @osu.command("unlink") #@audit-ok
    async def unlink_account(self, event: AstrMessageEvent):
        """
        解除平台 ID 的关联
        """
        platform_id = event.get_sender_id()
        
        # 检查是否已关联
        existing_osu_id = self.link_account_manager.get_osu_id_by_platform(platform_id)
        if not existing_osu_id:
            await event.send(MessageChain([Comp.Plain(get_info("unlink.not_linked"))]))
            return
        
        try:
            # 解除关联
            success = self.link_account_manager.unlink_account(platform_id)
            if success:
                # 同时删除 token
                oauth_client = OsuOAuthClient(
                    client_id=self.client_id or 0,
                    client_secret=self.client_secret or "",
                    redirect_uri=self.redirect_uri
                )
                oauth_client.remove_token(platform_id)
                
                await event.send(MessageChain([Comp.Plain(
                    get_info("unlink.success", osu_id=existing_osu_id)
                )]))
                logger.info(f"解除 OSU 账号关联: {existing_osu_id} <-> {platform_id}")
            else:
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.error_generic", operation="解除关联", error="未知错误")
                )]))
        except Exception as e:
            logger.error(f"解除 OSU 账号关联失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="解除关联", error=str(e))
            )]))

    @osu.command("me") #@audit-ok
    async def get_me(self, event: AstrMessageEvent, mode: str = None):
        """
        获取当前关联账号的用户信息
        """
        # 检查用户认证状态（需要 identify 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.IDENTIFY])
        if not auth_ok:
            return
        
        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="个人"))]))
            
            # 获取用户信息
            user_info = await self.osu_client.get_own_data(platform_id, mode)
            
            # 格式化用户信息
            avatar_url, user_message = self._format_user_info(user_info, is_self=True)
            
            # 构建消息链
            chain = []
            if avatar_url:
                chain.append(Comp.Image.fromURL(avatar_url))
            chain.append(Comp.Plain(user_message))
            
            await event.send(MessageChain(chain))
            
        except Exception as e:
            logger.error(f"获取个人 OSU 信息失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="获取个人信息", error=str(e))
            )]))

    @osu.command("user") #@audit-ok
    async def get_user(self, event: AstrMessageEvent, user: str, mode: str = None, type: str = None):
        """
        查询指定用户的信息
        
        Args:
            user: 用户名或用户ID
            mode: 游戏模式 (osu, taiko, fruits, mania)
            type: 查询类型 (id, name) - 指定输入是用户ID还是用户名
        """
        if not user:
            await event.send(MessageChain([Comp.Plain(get_info("user.usage"))]))
            return
        
        # 检查用户认证状态（不需要 identify 权限，只需要 public 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        # 验证 type 参数
        if type and type not in ['id', 'name']:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="查询类型", error="无效的查询类型")
            )]))
            return
        
        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.querying_user", user=user))]))
            
            # 根据 type 参数处理用户输入
            processed_user = user
            if type == 'id':
                # 强制按 ID 查询
                if user.isdigit():
                    processed_user = int(user)
                else:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="查询用户", error=f"指定为 ID 查询，但输入 '{user}' 不是有效的数字ID")
                    )]))
                    return
            elif type == 'name':
                # 强制按用户名查询，确保有 @ 前缀
                if not user.startswith('@'):
                    processed_user = f"@{user}"
            else:
                # 自动检测模式（默认行为）
                if user.isdigit():
                    processed_user = int(user)
                elif not user.startswith('@'):
                    processed_user = f"@{user}"
            
            # 获取用户信息
            user_info = await self.osu_client.get_user(platform_id, processed_user, mode)
            
            # 格式化用户信息
            avatar_url, user_message = self._format_user_info(user_info)
            
            # 构建消息链
            chain = []
            if avatar_url:
                chain.append(Comp.Image.fromURL(avatar_url))
            chain.append(Comp.Plain(user_message))
            
            await event.send(MessageChain(chain))
            
        except Exception as e:
            logger.error(f"查询用户 {user} 信息失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="查询用户", error=str(e))
            )]))

    @osu.command("users") #@audit-ok
    async def get_users(self, event: AstrMessageEvent):
        """
        批量查询多个用户的信息
        通过对话模式获取用户ID列表
        """
        # 检查用户认证状态（不需要 identify 权限，只需要 public 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        # 发送提示信息
        await event.send(MessageChain([Comp.Plain(get_info("batch_query.users_prompt"))]))
        
        # 等待用户输入用户ID列表
        @session_waiter(timeout=300)  # 5分钟超时
        async def handle_user_ids_input(controller: SessionController, event: AstrMessageEvent):
            try:
                user_input = event.message_str.strip()
                
                # 检查是否取消
                if user_input.lower() in ['取消', 'cancel', '退出', 'quit']:
                    await event.send(MessageChain([Comp.Plain(get_info("common.cancel", type="批量查询"))]))
                    controller.stop()
                    return
                
                # 解析用户ID列表
                user_ids = user_input.split()
                if not user_ids:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="批量查询", error="请提供至少一个用户ID")
                    )]))
                    controller.keep(60)  # 继续等待 60 秒
                    return
                
                # 检查数量限制
                if len(user_ids) > 50:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="批量查询", error=f"最多支持同时查询 50 个用户\n您提供了 {len(user_ids)} 个用户ID\n请重新发送，减少用户ID数量")
                    )]))
                    controller.keep(60)
                    return
                
                # 转换用户ID列表，支持字符串和数字
                processed_ids = []
                invalid_ids = []
                
                for uid in user_ids:
                    if uid.isdigit():
                        processed_ids.append(int(uid))
                    else:
                        # 对于非数字ID，检查是否为有效格式
                        if len(uid) > 0 and not uid.isspace():
                            processed_ids.append(str(uid))
                        else:
                            invalid_ids.append(uid)
                
                # 如果有无效ID，提示用户
                if invalid_ids:
                    await event.send(MessageChain([Comp.Plain( 
                        get_info("common.warning_generic", operation="批量查询", warning=f"发现无效的用户ID: {', '.join(invalid_ids)}\n将继续查询其余 {len(processed_ids)} 个有效ID")
                    )]))
                
                if not processed_ids:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="批量查询", error="没有找到有效的用户ID")
                    )]))
                    controller.keep(60)
                    return
                
                await event.send(MessageChain([Comp.Plain(get_info("common.querying", count=len(processed_ids), type="用户"))]))
                
                # 批量获取用户信息
                users_info = await self.osu_client.get_users(platform_id, processed_ids)
                
                if not users_info:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("common.error_generic", operation="查询用户", error="没有找到任何用户信息\n请检查用户ID是否正确")
                    )]))
                    controller.stop()
                    return
                
                # 发送概览信息
                await event.send(MessageChain([Comp.Plain(get_info("common.querying", count=len(users_info), type="用户"))]))
                
                # 为每个用户单独发送信息
                for i, user_info in enumerate(users_info, 1):
                    # 格式化用户信息
                    avatar_url, user_message = self._format_user_info(user_info)
                    
                    # 构建消息链
                    chain = []
                    if avatar_url:
                        chain.append(Comp.Image.fromURL(avatar_url))
                    
                    # 添加序号前缀
                    prefixed_message = f"【{i}/{len(users_info)}】\n{user_message}"
                    chain.append(Comp.Plain(prefixed_message))
                    
                    # 发送单个用户信息
                    await event.send(MessageChain(chain))
                    
                    # 稍微延迟避免消息发送过快
                    if i < len(users_info):  # 最后一个不需要延迟
                        await asyncio.sleep(0.5)
                
                controller.stop()
                
            except Exception as e:
                logger.error(f"批量查询用户信息失败: {e}")
                await event.send(MessageChain([Comp.Plain( 
                    get_info("common.error_generic", operation="批量查询", error=str(e))
                )]))
                controller.stop()
        
        # 开始等待用户输入
        try:
            await handle_user_ids_input(event)
        except TimeoutError:
            await event.send(MessageChain([Comp.Plain(
                get_info("batch_query.timeout", command="users")
            )]))

    @osu.command("update") #@audit-ok
    async def update(self, event: AstrMessageEvent, mode: str = None):
        """
        上传用户成绩至 OSU!track
        
        Args:
            mode: 游戏模式 (osu, taiko, fruits, mania)，默认为 osu
        """
        # 检查用户认证状态（不需要 identify 权限，只需要 public 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        try:
            # 验证和标准化模式
            validated_mode = validate_osu_mode(mode or "osu")
            
            # 转换为 OSU Track 模式
            track_mode = convert_osu_mode_to_track_mode(validated_mode)

            await event.send(MessageChain([Comp.Plain(get_info("common.uploading", mode=validated_mode.upper()))]))

            # 调用 OSU Track API 更新用户数据
            update_response = await self.osu_track_client.update_user(osu_id, track_mode)
            
            # 准备格式化参数
            stats = update_response.update
            format_params = {
                "username": update_response.username,
                "mode": validated_mode.upper(),
                "new_hs_count": len(update_response.newhs) if update_response.newhs else 0,
                "pp_change": f"{stats.pp:+.2f}" if stats and stats.pp is not None else "-",
                "rank_change": f"{stats.rank:+d}" if stats and stats.rank is not None else "-",
                "country_rank_change": f"{stats.country_rank:+d}" if stats and stats.country_rank is not None else "-",
                "accuracy_change": f"{stats.accuracy:+.2f}%" if stats and stats.accuracy is not None else "-",
            }
            
            # 发送成功消息
            await event.send(MessageChain([Comp.Plain(get_info("update.success", **format_params))]))
            
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(get_info("update.param_error", error=str(e)))]))
        except Exception as e:
            logger.error(f"上传成绩到 OSU!track 失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="上传成绩", error=str(e))
            )]))

    @osu.command("map") #@audit-ok
    async def get_beatmap(self, event: AstrMessageEvent, beatmap_id: str):
        """
        查询指定谱面的详细信息
        
        Args:
            beatmap_id: 谱面ID
        """
        if not beatmap_id:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.map_usage"))]))
            return
        
        # 验证谱面ID格式
        if not beatmap_id.isdigit():
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.invalid_id", id=beatmap_id))]))
            return
        
        # 检查用户认证状态（需要 public 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.querying_beatmap", id=beatmap_id))]))
            
            # 获取谱面信息
            beatmap_info = await self.osu_client.get_beatmap(platform_id, int(beatmap_id))
            
            # 格式化谱面信息
            beatmap_message = self._format_beatmap_info(beatmap_info)
            
            await event.send(MessageChain([Comp.Plain(beatmap_message)]))
            
        except Exception as e:
            logger.error(f"查询谱面 {beatmap_id} 信息失败: {e}")
            await event.send(MessageChain([Comp.Plain( 
                get_info("common.error_generic", operation="查询谱面", error=str(e))
            )]))

    @osu.command("mapset") #@audit-ok
    async def get_beatmapset(self, event: AstrMessageEvent, mapset_id: str):
        """
        查询指定谱面集的详细信息
        
        Args:
            mapset_id: 谱面集ID
        """
        if not mapset_id:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.mapset_usage"))]))
            return
        
        # 验证谱面集ID格式
        if not mapset_id.isdigit():
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.invalid_mapset_id", id=mapset_id))]))
            return
        
        # 检查用户认证状态（需要 public 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.querying_beatmapset", id=mapset_id))]))
            
            # 获取谱面集信息
            beatmapset_info = await self.osu_client.get_beatmapset(platform_id, int(mapset_id))
            
            # 格式化谱面集信息
            cover_url, beatmapset_message = self._format_beatmapset_info(beatmapset_info)
            
            # 构建消息链
            chain = []
            if cover_url:
                chain.append(Comp.Image.fromURL(cover_url))
            chain.append(Comp.Plain(beatmapset_message))
            
            await event.send(MessageChain(chain))
            
        except Exception as e:
            logger.error(f"查询谱面集 {mapset_id} 信息失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                f"❌ 查询谱面集 {mapset_id} 失败: {str(e)}\n"
                "请检查谱面集ID是否正确，或稍后重试"
            )]))

    @osu.command("mapsets") #@audit-ok
    async def get_beatmapsets(self, event: AstrMessageEvent):
        """
        批量查询多个谱面集的信息
        通过对话模式获取谱面集ID列表
        """
        # 检查用户认证状态（需要 public 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        # 发送提示信息
        prompt_message = get_info("batch_query.mapsets_prompt")
        
        await event.send(MessageChain([Comp.Plain(prompt_message)]))
        
        # 等待用户输入谱面集ID列表
        @session_waiter(timeout=300)  # 5分钟超时
        async def handle_mapset_ids_input(controller: SessionController, event: AstrMessageEvent):
            try:
                user_input = event.message_str.strip()
                
                # 检查是否取消
                if user_input.lower() in ['取消', 'cancel', '退出', 'quit']:
                    await event.send(MessageChain([Comp.Plain(get_info("common.cancel", type="批量查询"))]))
                    controller.stop()
                    return
                
                # 解析谱面集ID列表
                mapset_ids = user_input.split()
                if not mapset_ids:
                    await event.send(MessageChain([Comp.Plain(get_info("batch_query.no_ids", type="谱面集"))]))
                    controller.keep(60)  # 继续等待 60 秒
                    return
                
                # 检查数量限制
                if len(mapset_ids) > 20:
                    await event.send(MessageChain([Comp.Plain(get_info("batch_query.too_many", type="谱面集", count=len(mapset_ids), max=20))]))
                    controller.keep(60)
                    return
                
                # 验证谱面集ID格式
                valid_ids = []
                invalid_ids = []
                
                for mapset_id in mapset_ids:
                    if mapset_id.isdigit():
                        valid_ids.append(int(mapset_id))
                    else:
                        invalid_ids.append(mapset_id)
                
                # 如果有无效ID，提示用户
                if invalid_ids:
                    await event.send(MessageChain([Comp.Plain(get_info("batch_query.invalid_ids", type="谱面集", ids=', '.join(invalid_ids), valid_count=len(valid_ids)))]))
                
                if not valid_ids:
                    await event.send(MessageChain([Comp.Plain(get_info("batch_query.no_valid_ids", type="谱面集"))]))
                    controller.keep(60)
                    return
                
                await event.send(MessageChain([Comp.Plain(get_info("common.querying", count=len(valid_ids), type="谱面集"))]))
                
                # 逐个获取谱面集信息
                successful_count = 0
                failed_count = 0
                
                for i, mapset_id in enumerate(valid_ids, 1):
                    try:
                        # 获取谱面集信息
                        beatmapset_info = await self.osu_client.get_beatmapset(platform_id, mapset_id)
                        
                        # 格式化谱面集信息
                        cover_url, beatmapset_message = self._format_beatmapset_info(beatmapset_info)
                        
                        # 构建消息链
                        chain = []
                        if cover_url:
                            chain.append(Comp.Image.fromURL(cover_url))
                        
                        # 添加序号前缀
                        prefixed_message = f"【{i}/{len(valid_ids)}】\n{beatmapset_message}"
                        chain.append(Comp.Plain(prefixed_message))
                        
                        # 发送单个谱面集信息
                        await event.send(MessageChain(chain))
                        successful_count += 1
                        
                        # 稍微延迟避免发送过快
                        if i < len(valid_ids):  # 最后一个不需要延迟
                            await asyncio.sleep(0.5)
                            
                    except Exception as e:
                        logger.error(f"查询谱面集 {mapset_id} 失败: {e}")
                        await event.send(MessageChain([Comp.Plain(
                            f"❌ 【{i}/{len(valid_ids)}】查询谱面集 {mapset_id} 失败: {str(e)}"
                        )]))
                        failed_count += 1
                
                # 发送总结信息
                summary_message = f"✅ 批量查询完成！成功: {successful_count}, 失败: {failed_count}"
                await event.send(MessageChain([Comp.Plain(summary_message)]))
                
                controller.stop()
                
            except Exception as e:
                logger.error(f"批量查询谱面集信息失败: {e}")
                await event.send(MessageChain([Comp.Plain(
                    f"❌ 批量查询失败: {str(e)}\n"
                    "请检查谱面集ID是否正确，或稍后重试"
                )]))
                controller.stop()
        
        # 开始等待用户输入
        try:
            await handle_mapset_ids_input(event)
        except TimeoutError:
            await event.send(MessageChain([Comp.Plain(get_info("batch_query.timeout", command="mapsets"))]))

    @osu.command("friend") #@audit-ok
    async def get_friends(self, event: AstrMessageEvent):
        """
        获取好友列表
        显示每个好友的头像、昵称和在线状态
        """
        # 检查用户认证状态（需要 friends.read 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.FRIENDS])
        if not auth_ok:
            return
        
        try:
            await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="好友列表"))]))
            
            # 获取好友列表
            friends = await self.osu_client.get_friends(platform_id)
            
            if not friends:
                await event.send(MessageChain([Comp.Plain(get_info("friend.empty"))]))
                return
            
            # OSU API 的 /friends 端点返回的是用户信息列表，不是好友关系对象
            # 所有返回的用户都是好友，我们直接显示他们
            
            # 发送好友总数概览
            total_count = len(friends)
            
            overview_message = (
                f"👥 好友列表 (共 {total_count} 个)\n"
                f"正在逐个发送好友信息..."
            )
            await event.send(MessageChain([Comp.Plain(overview_message)]))
            
            # 发送所有好友信息
            for i, friend in enumerate(friends, 1):
                await self._send_friend_info(event, friend, i, total_count, "👥")
                if i < total_count:  # 最后一个不需要延迟
                    await asyncio.sleep(0.3)  # 避免发送过快
            
        except Exception as e:
            logger.error(f"获取好友列表失败: {e}")
            await event.send(MessageChain([Comp.Plain(get_info("friend.error", error=str(e)))]))

    def _get_rank_color(self, rank: str) -> str:
        """
        根据评级返回对应的颜色
        
        Args:
            rank: 评级 (XH, X, SH, S, A, B, C, D)
            
        Returns:
            str: 颜色代码
        """
        rank_colors = {
            'XH': '#FFD700',  # 金色 SS
            'X': '#C0C0C0',   # 银色 SS
            'SH': '#FFD700',  # 金色 S
            'S': '#C0C0C0',   # 银色 S
            'A': '#00FF00',   # 绿色
            'B': '#4169E1',   # 蓝色
            'C': '#FF00FF',   # 紫色
            'D': '#FF0000',   # 红色
            'F': '#808080'    # 灰色
        }
        return rank_colors.get(rank.upper(), '#808080')
    
    def _get_rank_marker(self, rank: str) -> str:
        """
        根据评级返回对应的标记样式
        
        Args:
            rank: 评级
            
        Returns:
            str: matplotlib 标记样式
        """
        rank_markers = {
            'XH': '*',  # 星形
            'X': '*',
            'SH': 'D',  # 菱形
            'S': 'D',
            'A': 'o',   # 圆形
            'B': 's',   # 方形
            'C': '^',   # 三角形
            'D': 'v',   # 倒三角
            'F': 'x'    # 叉形
        }
        return rank_markers.get(rank.upper(), 'o')
    
    async def _generate_pp_chart(self, stats_history: List[StatsUpdate], 
                                 hiscores: List[RecordedScore],
                                 username: str, mode: str, days: int) -> BytesIO:
        """
        生成 PP 图表（包含 PP 变化曲线和成绩散点图）
        
        Args:
            stats_history: 统计历史数据
            hiscores: 高分记录数据
            username: 用户名
            mode: 游戏模式
            days: 天数范围
            
        Returns:
            BytesIO: 图表图片的字节流
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        fig.suptitle(f'{username} - {mode.upper()} Mode PP Statistics (Last {days} Days)', 
                    fontsize=16, fontweight='bold')
        
        # 绘制 PP 变化曲线
        if stats_history:
            timestamps = [datetime.datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) 
                         for s in stats_history]
            pp_values = [s.pp_raw for s in stats_history]
            
            ax1.plot(timestamps, pp_values, color='#FF66AA', linewidth=2, marker='o', 
                    markersize=4, label='PP')
            ax1.set_xlabel('Date', fontsize=12)
            ax1.set_ylabel('PP', fontsize=12)
            ax1.set_title('PP Over Time', fontsize=14, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # 格式化 x 轴日期
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax1.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # 绘制成绩散点图
        if hiscores:
            score_times = [datetime.datetime.fromisoformat(s.score_time.replace('Z', '+00:00')) 
                          for s in hiscores]
            score_pps = [s.pp for s in hiscores]
            
            # 按评级分组绘制
            ranks = {}
            for score in hiscores:
                if score.rank not in ranks:
                    ranks[score.rank] = {'times': [], 'pps': []}
                ranks[score.rank]['times'].append(
                    datetime.datetime.fromisoformat(score.score_time.replace('Z', '+00:00'))
                )
                ranks[score.rank]['pps'].append(score.pp)
            
            # 为每个评级绘制散点
            for rank, data in ranks.items():
                ax2.scatter(data['times'], data['pps'], 
                           c=self._get_rank_color(rank),
                           marker=self._get_rank_marker(rank),
                           s=100, alpha=0.6, label=f'Rank {rank}',
                           edgecolors='black', linewidths=0.5)
            
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('PP', fontsize=12)
            ax2.set_title('Score Performance (PP by Rank)', fontsize=14, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='upper left', fontsize=8, ncol=2)
            
            # 格式化 x 轴日期
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        
        # 保存到字节流
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        return buf
    
    async def _generate_rank_chart(self, stats_history: List[StatsUpdate],
                                   username: str, mode: str, days: int) -> BytesIO:
        """
        生成排名变化图表
        
        Args:
            stats_history: 统计历史数据
            username: 用户名
            mode: 游戏模式
            days: 天数范围
            
        Returns:
            BytesIO: 图表图片的字节流
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.suptitle(f'{username} - {mode.upper()} Mode Rank Statistics (Last {days} Days)', 
                    fontsize=16, fontweight='bold')
        
        if stats_history:
            timestamps = [datetime.datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) 
                         for s in stats_history]
            ranks = [s.pp_rank for s in stats_history]
            
            ax.plot(timestamps, ranks, color='#66B2FF', linewidth=2, marker='o', 
                   markersize=4, label='Global Rank')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Rank', fontsize=12)
            ax.set_title('Global Rank Over Time', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # 反转 y 轴（排名越小越好）
            ax.invert_yaxis()
            
            # 格式化 x 轴日期
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        
        # 保存到字节流
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        return buf
    
    async def _generate_accuracy_chart(self, stats_history: List[StatsUpdate],
                                       username: str, mode: str, days: int) -> BytesIO:
        """
        生成准确率变化图表
        
        Args:
            stats_history: 统计历史数据
            username: 用户名
            mode: 游戏模式
            days: 天数范围
            
        Returns:
            BytesIO: 图表图片的字节流
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.suptitle(f'{username} - {mode.upper()} Mode Accuracy Statistics (Last {days} Days)', 
                    fontsize=16, fontweight='bold')
        
        if stats_history:
            timestamps = [datetime.datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) 
                         for s in stats_history]
            accuracies = [s.accuracy for s in stats_history]
            
            ax.plot(timestamps, accuracies, color='#FFB366', linewidth=2, marker='o', 
                   markersize=4, label='Accuracy')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Accuracy (%)', fontsize=12)
            ax.set_title('Accuracy Over Time', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # 设置 y 轴范围（准确率通常在 90-100 之间）
            if accuracies:
                min_acc = min(accuracies)
                max_acc = max(accuracies)
                padding = (max_acc - min_acc) * 0.1 or 1
                ax.set_ylim(min_acc - padding, max_acc + padding)
            
            # 格式化 x 轴日期
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        
        # 保存到字节流
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        return buf

    @osu.command("chart") #@audit-ok
    async def get_chart(self, event: AstrMessageEvent, mode: str = "osu", days: int = 30, type: str = "pp"):
        """
        返回成绩统计图表
        
        Args:
            mode: 游戏模式 (osu, taiko, fruits, mania)
            days: 天数范围
            type: 图表类型 (pp, rank, accuracy)
        """
        # 检查用户认证状态（需要 public 权限）
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        # 验证参数
        if type not in ['pp', 'rank', 'accuracy', 'acc']:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", 
                        operation="生成图表", 
                        error=f"无效的图表类型: {type}\n支持的类型: pp, rank, accuracy")
            )]))
            return
        
        if days < 1 or days > 365:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic",
                        operation="生成图表",
                        error="天数范围必须在 1-365 之间")
            )]))
            return
        
        try:
            # 验证和转换模式
            validated_mode = validate_osu_mode(mode)
            track_mode = convert_osu_mode_to_track_mode(validated_mode)
            
            # 确认时间，使用YYYY-MM-DD格式
            to_date = datetime.datetime.now(datetime.timezone.utc)
            from_date = to_date - timedelta(days=days)
            from_date_str = from_date.strftime("%Y-%m-%d")
            to_date_str = to_date.strftime("%Y-%m-%d")
            
            await event.send(MessageChain([Comp.Plain(
                get_info("common.loading", type=f"{type.upper()} 图表")
            )]))
            
            # 获取统计历史数据
            stats_history = await self.osu_track_client.get_stats_history(
                osu_id, track_mode, from_date_str, to_date_str
            )
            
            if not stats_history:
                await event.send(MessageChain([Comp.Plain(
                    get_info("common.error_generic",
                            operation="获取统计数据",
                            error=f"在过去 {days} 天内没有找到任何统计数据")
                )]))
                return
            
            # 获取用户名
            user_info = await self.osu_client.get_own_data(platform_id, validated_mode)
            username = user_info.username
            
            # 根据类型生成对应的图表
            if type == 'pp':
                # PP 图表需要额外获取高分数据
                hiscores = await self.osu_track_client.get_hiscores(
                    osu_id, track_mode, from_date_str, to_date_str
                )
                chart_buf = await self._generate_pp_chart(
                    stats_history, hiscores, username, validated_mode, days
                )
            elif type == 'rank':
                chart_buf = await self._generate_rank_chart(
                    stats_history, username, validated_mode, days
                )
            else:  # accuracy or acc
                chart_buf = await self._generate_accuracy_chart(
                    stats_history, username, validated_mode, days
                )
            
            # 发送图表（直接使用原始 PNG bytes）
            chart_bytes = chart_buf.read()
            await event.send(MessageChain([
                Comp.Image.fromBytes(chart_bytes)
            ]))
            
        except ValueError as e:
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="参数验证", error=str(e))
            )]))
        except Exception as e:
            logger.error(f"生成图表失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                get_info("common.error_generic", operation="生成图表", error=str(e))
            )]))

    @osu.group("search")
    def search(self, event: AstrMessageEvent):
        pass

    @search.command("map") #@audit-ok
    async def search_map(self, event: AstrMessageEvent, query: str, num_per_page: int, page_num: int, flag: str = None):
        """
        搜索谱面

        Args:
            query: 搜索关键词
            num_per_page: 每页显示的谱面数量
            page_num: 页码
            flag: 启用高级搜索flag
        """
        
        auth_ok, platform_id, osu_id = await self._check_user_authentication(event, [Scopes.PUBLIC])
        if not auth_ok:
            return
        
        # 参数验证
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
            if flag == "advanced":
                # 处理高级搜索逻辑
                prompt_message = get_info("beatmap.advanced_search_prompt")
                await event.send(MessageChain([Comp.Plain(prompt_message)]))
                
                # 设置会话等待高级搜索参数
                @session_waiter(timeout=300)
                async def handle_advanced_search_input(controller: SessionController, event: AstrMessageEvent):
                    try:
                        user_input = event.message_str.strip()
                        
                        # 检查是否取消
                        if user_input.lower() in ['取消', 'cancel', '退出', 'quit']:
                            await event.send(MessageChain([Comp.Plain(get_info("common.cancel", type="高级搜索"))]))
                            controller.stop()
                            return
                        
                        # 解析高级搜索参数
                        params = self._parse_advanced_search_params(user_input)
                        
                        await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="高级搜索"))]))
                        
                        # API不支持分页的排序方式，需要手动分页
                        paginated_results = None
                        if "sort" in params and params["sort"] not in ["relevance_desc", "updated_desc"]:
                            all_results = await self.osu_client.search_beatmapsets(query=query, **params)
                            start_index = (page_num - 1) * num_per_page
                            end_index = start_index + num_per_page
                            paginated_results = all_results[start_index:end_index]
                            search_results = all_results  # 用于获取总数
                        else:
                            params["page"] = page_num
                            search_results = await self.osu_client.search_beatmapsets(query=query, **params)

                        # 处理和发送结果
                        await self._process_search_results(
                            event, 
                            paginated_results if paginated_results is not None else search_results.beatmapsets,
                            num_per_page, 
                            page_num, 
                            "高级搜索",
                            total_results=len(search_results)
                        )
                        
                        controller.stop()
                    except Exception as e:
                        logger.error(f"高级搜索失败: {e}")
                        await event.send(MessageChain([Comp.Plain(
                            get_info("beatmap.advanced_search_error", error=str(e))
                        )]))
                        controller.stop()

                try:
                    await handle_advanced_search_input(event)
                except TimeoutError:
                    await event.send(MessageChain([Comp.Plain(
                        get_info("batch_query.timeout", command="高级搜索")
                    )]))
                return
            else:
                # 处理普通搜索逻辑
                await event.send(MessageChain([Comp.Plain(f"🔄 正在搜索谱面：{query}...")]))
                
                # 执行普通搜索
                await event.send(MessageChain([Comp.Plain(get_info("common.loading", type="搜索"))]))
                search_results = await self.osu_client.search_beatmapsets(query=query, page=page_num)
                await self._process_search_results(event, search_results.beatmapsets, num_per_page, page_num, "搜索", total_results=len(search_results))
        except Exception as e:
            logger.error(f"搜索谱面失败: {e}")
            await event.send(MessageChain([Comp.Plain(
                f"❌ 搜索失败: {str(e)}\n"
                "请检查搜索参数，或稍后重试"
            )]))

    #------- 辅助方法 -------#
    async def _process_search_results(self, event: AstrMessageEvent, results: list, num_per_page: int, page_num: int, search_type: str, total_results: int = 0):
        """
        处理搜索结果并发送消息
        
        Args:
            event: 消息事件
            search_results: 搜索结果对象
            num_per_page: 每页数量
            page_num: 页码
            search_type: 搜索类型（用于显示）
        """
        if not results:
            await event.send(MessageChain([Comp.Plain(get_info("beatmap.search_no_results"))]))
            return

        # 计算总页数
        total_pages = (total_results + num_per_page - 1) // num_per_page if total_results > 0 else 1
        
        # 发送概览
        overview_message = get_info(
            "beatmap.search_overview",
            type=search_type,
            count=len(results),
            total=total_results,
            page=page_num,
            total_pages=total_pages
        )
        await event.send(MessageChain([Comp.Plain(overview_message)]))
        
        # 逐个发送结果
        for i, beatmapset in enumerate(results, 1):
            message = self._format_beatmapset_info(beatmapset, show_beatmaps=False)
            
            # 添加序号
            prefix = f"【{i + (page_num - 1) * num_per_page}/{total_results}】\n" if total_results > 0 else f"【{i}】\n"
            
            # 构建消息链
            chain = []
            if beatmapset.card_url:
                try:
                    chain.append(Comp.Image.fromURL(beatmapset.card_url))
                except Exception as e:
                    logger.warning(f"无法加载谱面集卡片图片: {e}")
            
            chain.append(Comp.Plain(prefix + message))
            
            await event.send(MessageChain(chain))
            
            if i < len(results):
                await asyncio.sleep(0.5)
    
    async def _send_friend_info(self, event: AstrMessageEvent, friend, index: int, total: int, prefix: str):
        """
        发送好友信息
        
        Args:
            event: 消息事件
            friend: UserExtended 对象（好友用户信息）
            index: 当前索引
            total: 总数
            prefix: 前缀emoji
        """
        # friend 本身就是 UserExtended 对象，使用 _format_user_info 格式化
        avatar_url, user_message = self._format_user_info(friend)
        
        # 添加序号前缀
        prefixed_message = f"{prefix} 【{index}/{total}】\n{user_message}"
        
        # 构建消息链
        chain = []
        if avatar_url:
            try:
                chain.append(Comp.Image.fromURL(avatar_url))
            except Exception as e:
                logger.warning(f"无法加载用户头像: {e}")
        
        chain.append(Comp.Plain(prefixed_message))
        await event.send(MessageChain(chain))

    async def _check_user_authentication(self, event: AstrMessageEvent, require_scopes: list[Scopes] = None) -> tuple[bool, str, str]:
        """
        检查用户认证状态
        
        Args:
            event: 消息事件
            require_scopes: 需要的权限范围列表，如 [Scopes.PUBLIC] 或 [Scopes.IDENTIFY]
            
        Returns:
            tuple[bool, str, str]: (是否通过检查, 平台ID, OSU用户ID)
                                   如果检查失败，会自动发送错误消息
        """
        platform_id = event.get_sender_id()
        
        # 检查是否已关联
        existing_osu_id = self.link_account_manager.get_osu_id_by_platform(platform_id)
        if not existing_osu_id:
            await event.send(MessageChain([Comp.Plain(get_info("auth_check.not_linked"))]))
            return False, platform_id, ""
        
        # 检查是否有有效的 token
        if not self.osu_client.has_valid_token(platform_id):
            await event.send(MessageChain([Comp.Plain(get_info("auth_check.expired"))]))
            return False, platform_id, existing_osu_id
        
        # 如果需要特定权限，进行权限检查
        if require_scopes:
            missing_scopes = []
            for scope in require_scopes:
                scope_value = scope.value if isinstance(scope, Scopes) else str(scope)
                if not self.osu_client.check_scope_permission(platform_id, scope_value):
                    missing_scopes.append(scope_value)
            
            if missing_scopes:
                scopes_text = ", ".join(missing_scopes)
                await event.send(MessageChain([Comp.Plain(
                    get_info("auth_check.insufficient_scope", scopes=scopes_text)
                )]))
                return False, platform_id, existing_osu_id
        
        return True, platform_id, existing_osu_id
    
    def _format_user_info(self, user_info, is_self: bool = False) -> tuple[str, str]:
        """
        格式化用户信息
        
        Args:
            user_info: 用户信息对象
            is_self: 是否为当前用户自己
            
        Returns:
            tuple[str, str]: (头像URL, 格式化后的消息文本)
        """
        avatar_url = user_info.avatar_url
        
        # 构建基础信息
        message_parts = []
        message_parts.append(get_info("user.format.username", username=user_info.username))
        message_parts.append(get_info("user.format.user_id", id=user_info.id))
        
        if user_info.country_code:
            message_parts.append(get_info("user.format.country", country_code=user_info.country_code))
        
        # 添加统计信息
        if user_info.statistics:
            stats = user_info.statistics
            message_parts.append(get_info("user.format.statistics_header"))
            
            if stats.pp is not None:
                message_parts.append(get_info("user.format.pp", pp=f"{stats.pp:.2f}"))
            
            if stats.global_rank is not None:
                message_parts.append(get_info("user.format.global_rank", rank=f"{stats.global_rank:,}"))
            
            if stats.country_rank is not None:
                message_parts.append(get_info("user.format.country_rank", rank=f"{stats.country_rank:,}"))
            
            if stats.hit_accuracy is not None:
                message_parts.append(get_info("user.format.accuracy", accuracy=f"{stats.hit_accuracy:.2f}"))
            
            if stats.play_count is not None:
                message_parts.append(get_info("user.format.play_count", count=f"{stats.play_count:,}"))
            
            if stats.ranked_score is not None:
                message_parts.append(get_info("user.format.ranked_score", score=f"{stats.ranked_score:,}"))
            
            if stats.total_score is not None:
                message_parts.append(get_info("user.format.total_score", score=f"{stats.total_score:,}"))
            
            if stats.maximum_combo is not None:
                message_parts.append(get_info("user.format.max_combo", combo=f"{stats.maximum_combo:,}"))
        
        # 添加在线状态
        if user_info.is_online:
            message_parts.append(get_info("user.format.status_online"))
        else:
            message_parts.append(get_info("user.format.status_offline"))
        
        # 添加支持者状态
        if user_info.is_supporter:
            message_parts.append(get_info("user.format.supporter"))
        
        return avatar_url, "\n".join(message_parts)
    
    def _format_beatmap_info(self, beatmap_info) -> str:
        """
        格式化谱面信息
        
        Args:
            beatmap_info: 谱面信息对象
            
        Returns:
            str: 格式化后的消息文本
        """
        message_parts = []
        message_parts.append(get_info("beatmap.format.version", version=beatmap_info.version))
        message_parts.append(get_info("beatmap.format.beatmap_id", id=beatmap_info.id))
        message_parts.append(get_info("beatmap.format.beatmapset_id", beatmapset_id=beatmap_info.beatmapset_id))
        message_parts.append(get_info("beatmap.format.difficulty", rating=f"{beatmap_info.difficulty_rating:.2f}"))
        message_parts.append(get_info("beatmap.format.mode", mode=beatmap_info.mode))
        message_parts.append(get_info("beatmap.format.status", status=beatmap_info.status))
        
        # 添加详细参数
        if beatmap_info.bpm is not None:
            message_parts.append(get_info("beatmap.format.bpm", bpm=beatmap_info.bpm))
        
        if beatmap_info.ar is not None:
            message_parts.append(get_info("beatmap.format.ar", ar=beatmap_info.ar))
        
        if beatmap_info.cs is not None:
            message_parts.append(get_info("beatmap.format.cs", cs=beatmap_info.cs))
        
        if beatmap_info.drain is not None:
            message_parts.append(get_info("beatmap.format.hp", hp=beatmap_info.drain))
        
        # 添加物件数量
        if beatmap_info.count_circles is not None or beatmap_info.count_sliders is not None:
            message_parts.append(get_info("beatmap.format.objects_header"))
            if beatmap_info.count_circles is not None:
                message_parts.append(get_info("beatmap.format.circles", count=beatmap_info.count_circles))
            if beatmap_info.count_sliders is not None:
                message_parts.append(get_info("beatmap.format.sliders", count=beatmap_info.count_sliders))
            if beatmap_info.count_spinners is not None:
                message_parts.append(get_info("beatmap.format.spinners", count=beatmap_info.count_spinners))
        
        # 添加时长
        if beatmap_info.total_length is not None:
            minutes = beatmap_info.total_length // 60
            seconds = beatmap_info.total_length % 60
            message_parts.append(get_info("beatmap.format.duration", time=f"{minutes}:{seconds:02d}"))
        
        # 添加游戏数据
        if beatmap_info.playcount is not None:
            message_parts.append(get_info("beatmap.format.playcount", count=f"{beatmap_info.playcount:,}"))
        
        if beatmap_info.passcount is not None:
            message_parts.append(get_info("beatmap.format.passcount", count=f"{beatmap_info.passcount:,}"))
        
        return "\n".join(message_parts)
    
    def _format_beatmapset_info(self, beatmapset_info, show_beatmaps: bool = True) -> tuple[str, str]:
        """
        格式化谱面集信息
        
        Args:
            beatmapset_info: 谱面集信息对象
            show_beatmaps: 是否显示包含的谱面列表
            
        Returns:
            tuple[str, str]: (封面URL, 格式化后的消息文本)
        """
        cover_url = None
        if hasattr(beatmapset_info, 'covers') and beatmapset_info.covers:
            cover_url = beatmapset_info.covers.card or beatmapset_info.covers.cover
        elif hasattr(beatmapset_info, 'card_url'):
            cover_url = beatmapset_info.card_url
        
        message_parts = []
        message_parts.append(get_info("beatmap.mapset_format.title", title=beatmapset_info.title))
        
        if hasattr(beatmapset_info, 'artist'):
            message_parts.append(get_info("beatmap.mapset_format.artist", artist=beatmapset_info.artist))
        
        if hasattr(beatmapset_info, 'creator'):
            message_parts.append(get_info("beatmap.mapset_format.creator", creator=beatmapset_info.creator))
        
        message_parts.append(get_info("beatmap.mapset_format.id", id=beatmapset_info.id))
        
        if hasattr(beatmapset_info, 'status'):
            message_parts.append(get_info("beatmap.mapset_format.status", status=beatmapset_info.status))
        
        # 添加统计信息
        if hasattr(beatmapset_info, 'play_count') and beatmapset_info.play_count is not None:
            message_parts.append(get_info("beatmap.mapset_format.play_count", count=f"{beatmapset_info.play_count:,}"))
        
        if hasattr(beatmapset_info, 'favourite_count') and beatmapset_info.favourite_count is not None:
            message_parts.append(get_info("beatmap.mapset_format.favourite_count", count=f"{beatmapset_info.favourite_count:,}"))
        
        # 如果需要显示包含的谱面
        if show_beatmaps and hasattr(beatmapset_info, 'beatmaps') and beatmapset_info.beatmaps:
            message_parts.append(get_info("beatmap.mapset_format.beatmaps_header", total=len(beatmapset_info.beatmaps)))
            for beatmap in beatmapset_info.beatmaps[:5]:  # 最多显示5个
                message_parts.append(get_info("beatmap.mapset_format.beatmap_item", 
                                             version=beatmap.version, 
                                             rating=f"{beatmap.difficulty_rating:.2f}"))
            if len(beatmapset_info.beatmaps) > 5:
                message_parts.append(get_info("beatmap.mapset_format.beatmaps_more", 
                                             remaining=len(beatmapset_info.beatmaps) - 5))
        
        return cover_url, "\n".join(message_parts)

    async def terminate(self):
        return await super().terminate()