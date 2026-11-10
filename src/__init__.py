"""RSSHub 插件源包

提供 PLUGIN_DIR 常量供基础设施层引用。
"""

from pathlib import Path

# 插件根目录，供 PluginManager 等模块动态加载扩展使用
PLUGIN_DIR = Path(__file__).resolve().parent.parent
