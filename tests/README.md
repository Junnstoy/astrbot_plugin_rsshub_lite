# RssHub lite Tests

RssHub lite 插件的单元测试和集成测试套件。

## 运行测试

先在插件根目录安装开发依赖：`python -m pip install -r requirements-dev.txt`。以下入口均运行同一套 pytest 测试。

### 方法一：使用 Python（使用 pytest）

```bash
cd tests

# 运行所有测试
python run_tests.py

# 详细输出
python run_tests.py -v

# 仅运行单元测试
python run_tests.py --category unit

# 仅运行集成测试
python run_tests.py --category integration

# 快速模式
python run_tests.py --quick
```

### 方法二：使用 PowerShell

```powershell
cd tests

# 运行所有测试
.\run_tests.ps1

# 详细输出
.\run_tests.ps1 -Verbose

# 仅运行单元测试
.\run_tests.ps1 -Category unit

# 快速模式
.\run_tests.ps1 -Quick
```

### 方法三：使用 Bash（macOS / Linux）

```bash
cd tests

# 运行所有测试
./run_tests.sh

# 详细输出
./run_tests.sh --verbose

# 仅运行单元测试
./run_tests.sh --category unit

# 快速模式
./run_tests.sh --quick
```

Bash 脚本会优先使用当前激活的虚拟环境，再回退到 AstrBot 根目录的 `uv run python`、AstrBot `.venv` 和系统 Python。如需指定解释器，可使用：

```bash
RSSHUB_TEST_PYTHON=/path/to/python ./run_tests.sh --quick
```

### 方法四：直接使用 pytest

```bash
# 从 AstrBot 根目录安装测试与资源生成依赖
uv pip install --python .venv/bin/python -r data/plugins/astrbot_plugin_rsshub_lite/requirements-dev.txt

# 运行所有测试
uv run python -m pytest data/plugins/astrbot_plugin_rsshub_lite/tests/

# 详细输出
uv run python -m pytest data/plugins/astrbot_plugin_rsshub_lite/tests/ -v

# 仅运行单元测试
uv run python -m pytest data/plugins/astrbot_plugin_rsshub_lite/tests/unit/ -v

# 仅运行集成测试
uv run python -m pytest data/plugins/astrbot_plugin_rsshub_lite/tests/integration/ -v

# 显示覆盖率
uv run python -m pytest data/plugins/astrbot_plugin_rsshub_lite/tests/ --cov=src --cov-report=html
```

## 目录结构

```
tests/
├── README.md                 # 本文件
├── run_tests.py             # Python 测试运行器（pytest 分类入口）
├── run_tests.ps1            # PowerShell 测试运行器
├── run_tests.sh             # Bash 测试运行器（macOS / Linux）
├── conftest.py              # pytest 配置和 fixtures
├── mocks/                   # Mock 对象
│   ├── __init__.py
│   └── mock_data.py         # Mock 数据（Feed, Entry, Event 等）
├── fixtures/                # 测试数据文件
│   ├── feeds/               # RSS/Atom feed XML 文件
│   │   ├── simple_rss.xml
│   │   ├── atom_feed.xml
│   │   ├── rss_with_media.xml
│   │   └── rss_with_duplicate.xml
│   └── entries/             # 条目数据
├── unit/                    # 单元测试
│   ├── __init__.py
│   ├── application/         # 应用层测试
│   ├── domain/              # 领域层测试
│   ├── infrastructure/      # 基础设施层测试
│   │   ├── __init__.py
│   │   ├── test_rss_parser.py
│   │   └── ...
│   └── utils/               # 工具类测试
│       ├── __init__.py
│       └── ...
└── integration/             # 集成测试
    ├── __init__.py
    ├── test_deduplication.py
    ├── test_push_delivery.py
    └── test_end_to_end.py
```

## 测试覆盖

### 单元测试

| 模块 | 测试内容 |
|------|----------|
| `expression_parser` | 参数解析、表达式编译、嵌套属性访问 |
| `caching` | 内存缓存、缓存清理、过期策略 |
| `html_cleaner` | HTML 清理、标签剥离、XSS 防护 |
| `lock` | 锁管理器、锁复用、并发控制 |
| `rss_parser` | RSS 解析、Atom 解析、媒体提取 |
| `event_bus` | 事件发布/订阅、优先级、取消 |
| `plugin_manager` | 扩展注册/注销、优先级加载 |

### 集成测试

| 测试 | 内容 |
|------|------|
| `test_deduplication` | 条目去重逻辑、哈希计算 |
| `test_push_delivery` | 推送流程、消息格式化 |
| `test_end_to_end` | 完整 RSS 抓取-解析-推送流程 |

## Mock 对象

位于 `mocks/mock_data.py`：

- `MockFeedData` - 模拟 Feed 数据
- `MockEntryData` - 模拟 Entry 数据
- `MockAstrMessageEvent` - 模拟 AstrBot 消息事件
- `MockContext` - 模拟 AstrBot 上下文

## Fixtures

位于 `conftest.py`：

- `sample_rss_feed` - 简单 RSS feed XML
- `sample_atom_feed` - Atom feed XML
- `sample_media_feed` - 带媒体的 RSS feed
- `sample_duplicate_feed` - 有重复条目的 feed
- `mock_feed_entity` - Feed 实体
- `mock_subscription_entity` - Subscription 实体
- `sample_entries` - Entry 列表

## 添加新测试

在 `unit/` 或 `integration/` 目录创建 `test_*.py` 文件，pytest 和分类运行器都会自动收集，无需修改 `run_tests.py`：

```python
"""测试说明"""

from __future__ import annotations

import pytest


class TestYourFeature:
    """测试类说明"""

    def test_something(self, sample_rss_feed):
        """测试方法说明"""
        # 使用 fixture
        assert "rss" in sample_rss_feed

    async def test_async_feature(self):
        """异步测试"""
        result = await your_async_function()
        assert result is True
```

## PowerShell 命令

### 运行所有测试

```powershell
.\run_tests.ps1
```

### 运行特定类别

```powershell
.\run_tests.ps1 -Category unit
.\run_tests.ps1 -Category integration
```

### CI/CD 集成

```powershell
# 在 CI 中运行测试并检查退出码
.\run_tests.ps1 -Quick
exit $LASTEXITCODE
```

## 调试技巧

1. **使用 -v 查看详细输出**
2. **检查 fixtures 目录中的测试数据**
3. **使用 mocks 创建模拟对象**
4. **使用 pytest -x 在第一个失败时停止**
