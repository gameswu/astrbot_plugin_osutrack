"""
工具函数模块
"""
import yaml
import os
from astrbot.api import logger


# 缓存加载的数据，避免重复读取文件
_help_data_cache = None
_info_data_cache = None


def load_help_data():
    """
    从 help.yaml 加载帮助信息
    
    Returns:
        dict: 包含帮助信息的字典，如果加载失败则返回空字典
    """
    global _help_data_cache
    if _help_data_cache is not None:
        return _help_data_cache
    
    help_file_path = os.path.join(os.path.dirname(__file__), 'help.yaml')
    try:
        with open(help_file_path, 'r', encoding='utf-8') as f:
            _help_data_cache = yaml.safe_load(f)
            return _help_data_cache
    except FileNotFoundError:
        logger.error(f"help.yaml not found at {help_file_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing help.yaml: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading help.yaml: {e}")
        return {}


def load_info_data():
    """
    从 info.yaml 加载固定文本信息
    
    Returns:
        dict: 包含固定文本信息的字典，如果加载失败则返回空字典
    """
    global _info_data_cache
    if _info_data_cache is not None:
        return _info_data_cache
    
    info_file_path = os.path.join(os.path.dirname(__file__), 'info.yaml')
    try:
        with open(info_file_path, 'r', encoding='utf-8') as f:
            _info_data_cache = yaml.safe_load(f)
            return _info_data_cache
    except FileNotFoundError:
        logger.error(f"info.yaml not found at {info_file_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing info.yaml: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading info.yaml: {e}")
        return {}


def get_info(path, **kwargs):
    """
    从 info.yaml 获取指定路径的文本信息，并支持格式化
    
    Args:
        path: 点分隔的路径字符串，如 "link.auth_flow"
        **kwargs: 用于格式化文本的参数
    
    Returns:
        str: 格式化后的文本信息，如果找不到则返回空字符串
    
    Examples:
        >>> get_info("link.auth_flow", auth_url="https://example.com")
        >>> get_info("common.loading", type="用户")
        >>> get_info("batch_query.timeout", command="users")
    """
    info_data = load_info_data()
    
    # 按照点分隔的路径查找
    keys = path.split('.')
    current = info_data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            logger.warning(f"Info path not found: {path}")
            return ""
    
    # 如果结果是字符串，尝试格式化
    if isinstance(current, str):
        try:
            return current.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing format parameter for '{path}': {e}")
            return current
        except Exception as e:
            logger.error(f"Error formatting info text '{path}': {e}")
            return current
    
    return str(current) if current is not None else ""
