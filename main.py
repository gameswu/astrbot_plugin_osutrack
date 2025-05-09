import aiohttp
import json
import asyncio
import ossapi
from typing import Tuple, Optional, Dict, Any, List
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import random
import astrbot.api.message_components as Comp

class PluginFunctions:
    def __init__(self):
        self.api_key = None
        self.osu_client = None
        self.osutrack_api_url = "https://osutrack-api.ameo.dev/"
    
    def set_api_key(self, api_key):
        """设置API密钥并初始化客户端"""
        self.api_key = api_key
        # 使用正确的 osu API 客户端初始化方式
        if api_key:
            try:
                self.osu_client = ossapi.OssapiV1(api_key)
                logger.info("成功初始化 osu API 客户端")
            except Exception as e:
                logger.error(f"初始化 osu API 客户端失败: {str(e)}")
                self.osu_client = None
    
    async def update_user_score(self, user_id: str, mode: int = 0) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        更新用户成绩至 osu!track
        Args:
            user_id (str): 用户ID
            mode (int): 模式，0: osu!, 1: osu!taiko, 2: osu!catch, 3: osu!mania
        Returns:
            Tuple[bool, Optional[str], Optional[Dict[str, Any]]]: 
                - 成功标志
                - 用户名
                - API响应数据
        """
        if not user_id:
            logger.error("更新用户成绩失败: 未提供用户ID")
            return False, None, None
            
        try:
            # 验证模式
            mode_int = int(mode)
            if mode_int not in [0, 1, 2, 3]:
                logger.warning(f"更新用户成绩: 无效的模式值 {mode}，将使用默认模式 0")
                mode_int = 0
            
            # 调用osutrack API更新用户成绩
            url = f"{self.osutrack_api_url}update"
            params = {
                "user": user_id,
                "mode": str(mode_int)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        osutrack_response = await response.json()
                        
                        # 检查用户是否存在
                        username = osutrack_response.get("username")
                        exists = osutrack_response.get("exists", False)
                        
                        if exists:
                            logger.info(f"成功更新用户 {username} (ID: {user_id}) 在模式 {mode_int} 的成绩")
                            return True, username, osutrack_response
                        else:
                            logger.warning(f"用户 {username or user_id} 在模式 {mode_int} 无成绩更新")
                            return False, username, osutrack_response
                    else:
                        error_text = await response.text()
                        logger.error(f"OsuTrack API update失败: 状态码 {response.status}, 参数: {params}, 响应: {error_text}")
                        return False, None, None
                        
        except ValueError as e:
            logger.error(f"更新用户成绩失败: 模式参数转换错误 - {str(e)}")
            return False, None, None
        except Exception as e:
            logger.error(f"更新用户成绩时发生未知错误: {str(e)}")
            return False, None, None
    
    async def search_beatmap(self, since: str = None, count: int = 5, m: int = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        使用osu库查询谱面
        Args:
            since (str): 查询时间
            count (int): 返回数量
            m (int): 模式，0: osu!, 1: osu!taiko, 2: osu!catch, 3: osu!mania
        Returns:
            Tuple[bool, Optional[Dict[str, Any]]]: 
                - 成功标志
                - 经过处理后的API响应数据
        """
        if not self.osu_client:
            logger.error("查询谱面失败: 未初始化osu客户端")
            return False, None
        
        count = 10 if count > 10 else count
        count = 1 if count < 1 else count
        
        try:
            # 直接使用 ossapi 的同步方法
            beatmaps = self.osu_client.get_beatmaps(
                since=since,
                limit=500,
                mode=m
            )
            
            if not beatmaps:
                logger.warning("查询谱面失败: 未找到谱面")
                return False, None
            
            # 处理返回的谱面数据
            beatmap_data = {}
            for beatmap in beatmaps:
                beatmapset_id = getattr(beatmap, 'beatmapset_id', None)
                if beatmapset_id and beatmapset_id not in beatmap_data:
                    beatmap_data[beatmapset_id] = {
                        "beatmapset_id": beatmapset_id,
                        "approved": getattr(beatmap, 'approved', 'Unknown'),
                        "title": getattr(beatmap, 'title', 'Unknown'),
                        "artist": getattr(beatmap, 'artist', 'Unknown'),
                        "creator": getattr(beatmap, 'creator', 'Unknown'),
                        "creator_id": getattr(beatmap, 'creator_id', 'Unknown'),
                        "total_length": getattr(beatmap, 'total_length', 0),
                        "bpm": getattr(beatmap, 'bpm', 0),
                        "tags": getattr(beatmap, 'tags', ''),
                        "cover_url": f"https://assets.ppy.sh/beatmaps/{beatmapset_id}/covers/cover.jpg"
                    }

            # 限制返回数量
            if len(beatmap_data) >= count:
                beatmap_data = {k: beatmap_data[k] for k in random.sample(list(beatmap_data.keys()), min(count, len(beatmap_data)))}
            else:
                logger.warning(f"查询谱面成功: 返回 {len(beatmap_data)} 条谱面数据，但少于请求的数量 {count}")
            logger.info(f"查询谱面成功: 返回 {len(beatmap_data)} 条谱面数据")
            
            return True, beatmap_data
            
        except ValueError as e:
            logger.error(f"查询谱面失败: 参数错误 - {str(e)}")
            return False, None
        except Exception as e:
            logger.error(f"查询谱面失败: {str(e)}")
            return False, None
    
    async def get_user_info(self, user_id: str, mode: int = 0) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        获取用户信息
        Args:
            user_id (str): 用户ID
            mode (int): 模式，0: osu!, 1: osu!taiko, 2: osu!catch, 3: osu!mania
        Returns:
            Tuple[bool, Optional[Dict[str, Any]]]: 
                - 成功标志
                - 用户信息数据
        """
        if not self.osu_client:
            logger.error("获取用户信息失败: 未初始化osu客户端")
            return False, None
        
        try:
            # 使用 ossapi 的同步方法
            users = self.osu_client.get_user(user_id, mode=mode, user_type= "id")
            
            # ossapi 可能返回列表或单个对象
            user = users[0] if isinstance(users, list) and users else users
            
            if user:
                # 确保从对象中获取属性，或从字典中获取键值
                get_value = lambda obj, field, default: (
                    getattr(obj, field, None) if hasattr(obj, '__dict__') 
                    else obj.get(field, None) if isinstance(obj, dict) 
                    else default
                )
                
                user_id_value = get_value(user, 'user_id', user_id)
                user_data = {
                    "user_id": user_id_value,
                    "username": get_value(user, 'username', 'Unknown'),
                    "pp_rank": get_value(user, 'pp_rank', 0),
                    "pp_raw": get_value(user, 'pp_raw', 0),
                    "country": get_value(user, 'country', 'Unknown'),
                    "accuracy": get_value(user, 'accuracy', 0),
                    "level": get_value(user, 'level', 0),
                    "playcount": get_value(user, 'playcount', 0),
                    "count_rank_ss": get_value(user, 'count_rank_ss', 0),
                    "count_rank_ssh": get_value(user, 'count_rank_ssh', 0),
                    "count_rank_s": get_value(user, 'count_rank_s', 0),
                    "count_rank_sh": get_value(user, 'count_rank_sh', 0),
                    "count_rank_a": get_value(user, 'count_rank_a', 0),
                    "avatar_url": f"https://a.ppy.sh/{user_id_value}"
                }
                return True, user_data
            else:
                logger.warning(f"获取用户信息失败: 未找到用户 {user_id}")
                return False, None
                
        except ValueError as e:
            logger.error(f"获取用户信息失败: 模式参数转换错误 - {str(e)}")
            return False, None
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return False, None

@register("osutrack","gameswu","基于osu!track与osu!api的osu!成绩查询插件","0.1.0","https://github.com/gameswu/astrbot_plugin_osutrack")
class OsuTrackPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    async def initialize(self):
        self.api_key = self.config.get("api_key")
        self.functions = PluginFunctions()
        self.functions.set_api_key(api_key=self.api_key)

    @filter.command("osu_help")
    async def osu_help(self, event: AstrMessageEvent, cmd: str = None):
        """
        显示帮助信息
        """
        if not cmd:
            help_text = (
                "可用命令:\n"
                "- /osu_help <cmd>: 显示帮助信息\n"
                "- /osu_update [user_id] [mode]: 更新用户成绩\n"
                "- /osu_beatmap <count> <m> <since>: 查询谱面\n"
                "- /osu_user [user_id] [mode]: 查询用户信息\n"
                "~~~~~~~~\n"
                "[] 表示必填参数； <> 表示选填参数\n"
                "填写<cmd>可查看具体命令帮助，如 /osu_help osu_update"
            )
            yield event.plain_result(help_text)
        else:
            help_text = {
                "osu_help": "显示帮助信息",
                "osu_update": "更新用户成绩\n格式: /osu_update [user_id] [mode]\n参数说明:\n[user_id] 用户ID\n[mode] 模式 0: osu!, 1: osu!taiko, 2: osu!catch, 3: osu!mania",
                "osu_beatmap": "查询谱面，需要提供osu! API key\n格式: /osu_beatmap <count> <m> <since>\n参数说明:\n<count> 返回数量，默认5，在1～10之间取值\n<m> 模式 0: osu!, 1: osu!taiko, 2: osu!catch, 3: osu!mania\n<since> 查询自从该时间的谱面，格式: YYYY-MM-DD",
                "osu_user": "查询用户信息，需要提供osu! API key\n格式: /osu_user [user_id] [mode]\n参数说明:\n[user_id] 用户ID\n[mode] 模式 0: osu!, 1: osu!taiko, 2: osu!catch, 3: osu!mania"
            }
            if cmd in help_text:
                yield event.plain_result(f"{cmd}: {help_text[cmd]}")
            else:
                yield event.plain_result("未知命令，请使用 /osu_help 查看可用命令")

    @filter.command("osu_update")
    async def osu_update(self, event: AstrMessageEvent, user_id: str, mode: int):
        """
        上传成绩
        """
        result = await self.functions.update_user_score(user_id=user_id, mode=mode)
        if result[0]:
            newhs_count = len(result[2].get("newhs", []))
            osu_username = result[1]
            logger.info(f"成功更新用户 {osu_username} (ID: {user_id}) 在模式 {mode} 的成绩")
            yield event.plain_result(f"成功帮主人更新用户 {osu_username} (ID: {user_id}) 在模式 {mode} 的成绩喵~ 更新了 {newhs_count} 条新成绩喵呜")
        else:
            logger.warning(f"更新用户成绩失败: 用户ID {user_id}, 模式 {mode}, API返回空响应")
            yield event.plain_result(f"帮主人更新用户成绩失败了喵 用户ID {user_id}, 模式 {mode}, 不知道这个玩家玩过osu了没喵~")

    @filter.command("osu_beatmap")
    async def osu_beatmap(self, event: AstrMessageEvent, limit: int = 5, m: int = None, since: str = None):
        """
        查询谱面 需要api_key
        """
        if not self.api_key:
            logger.error("查询谱面失败: 未提供API密钥")
            yield event.plain_result("查询谱面失败了喵: 主人要提供API密钥小夜才可以查询谱面喵~")
            return

        result = await self.functions.search_beatmap(since=since, limit=limit, m=m)
        if result[0]:
            beatmap_data = result[1]
            if beatmap_data:
                for beatmap in beatmap_data.values():
                    chain = [
                        Comp.Image.fromURL(beatmap["cover_url"]),
                        Comp.Plain(
                            f"标题: {beatmap['title']}\n"
                            f"艺术家: {beatmap['artist']}\n"
                            f"作者: {beatmap['creator']} (ID: {beatmap['creator_id']})\n"
                            f"谱面链接: https://osu.ppy.sh/beatmapsets/{beatmap['beatmapset_id']}\n"
                            f"总时长: {beatmap['total_length']}秒\n"
                            f"BPM: {beatmap['bpm']}\n"
                            f"标签: {beatmap['tags']}\n"
                            f"谱面状态: {beatmap['approved']}\n"
                        )
                    ]
                    yield event.chain_result(chain)
                yield event.plain_result("查询谱面成功了喵~")
            else:
                yield event.plain_result("没有找到符合条件的谱面喵~")
        else:
            logger.warning(f"查询谱面失败: API返回空响应")
            yield event.plain_result("查询谱面失败了喵~")
    
    @filter.command("osu_user")
    async def osu_user(self, event: AstrMessageEvent, user_id: str, mode: int = 0):
        """
        查询用户信息 需要api_key
        """
        if not self.api_key:
            logger.error("查询用户信息失败: 未提供API密钥")
            yield event.plain_result("查询用户信息失败了喵: 主人要提供API密钥小夜才可以查询用户信息喵~")
            return
        
        result = await self.functions.get_user_info(user_id=user_id, mode=mode)
        if result[0]:
            user_data = result[1]
            mode_names = {0: "osu!", 1: "taiko", 2: "catch", 3: "mania"}
            mode_name = mode_names.get(mode, "osu!")
            
            chain = [
                Comp.Image.fromURL(user_data["avatar_url"]),
                Comp.Plain(
                    f"用户名: {user_data['username']} (ID: {user_data['user_id']})\n"
                    f"国家: {user_data['country']}\n"
                    f"游戏模式: {mode_name}\n"
                    f"PP: {user_data['pp_raw']}\n"
                    f"全球排名: #{user_data['pp_rank']}\n"
                    f"准确率: {user_data['accuracy']}%\n"
                    f"等级: {user_data['level']}\n"
                    f"游玩次数: {user_data['playcount']}\n"
                    f"SS+: {user_data['count_rank_ssh']} | SS: {user_data['count_rank_ss']}\n"
                    f"S+: {user_data['count_rank_sh']} | S: {user_data['count_rank_s']}\n"
                    f"A: {user_data['count_rank_a']}\n"
                    f"用户主页: https://osu.ppy.sh/users/{user_data['user_id']}"
                )
            ]
            yield event.chain_result(chain)
            yield event.plain_result("查询用户信息成功了喵~")
        else:
            logger.warning(f"查询用户信息失败: 未找到用户 {user_id}")
            yield event.plain_result(f"查询用户信息失败了喵: 未找到用户 {user_id} 喵~")

    async def terminate(self):
        return await super().terminate()