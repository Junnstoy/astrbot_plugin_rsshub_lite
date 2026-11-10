"""测试表达式解析器"""

from __future__ import annotations

import pytest
from astrbot_plugin_rsshub_lite.src.infrastructure.utils import (
    CompiledExpression,
    ExpressionEvaluator,
    ExpressionParser,
)


class TestExpressionParser:
    """测试 ExpressionParser 类"""

    def test_parse_simple_param(self):
        """测试解析简单参数"""
        args = ("value1", "value2")
        kwargs = {}
        result = ExpressionParser.parse("#0", args, kwargs)
        assert result == "value1"

    def test_parse_named_param(self):
        """测试解析命名参数"""
        args = ()
        kwargs = {"name": "test_value"}
        param_names = ["name"]
        result = ExpressionParser.parse("#name", args, kwargs, param_names)
        assert result == "test_value"

    def test_parse_nested_attribute(self):
        """测试解析嵌套属性"""

        class Obj:
            def __init__(self):
                self.id = 123
                self.name = "test"

        obj = Obj()
        args = (obj,)
        kwargs = {}
        result = ExpressionParser.parse("#0.id", args, kwargs)
        assert result == 123

    def test_parse_string_literal(self):
        """测试解析字符串字面量"""
        args = ()
        kwargs = {}
        result = ExpressionParser.parse("'hello world'", args, kwargs)
        assert result == "hello world"

    def test_parse_number_literal(self):
        """测试解析数字字面量"""
        args = ()
        kwargs = {}
        result = ExpressionParser.parse("42", args, kwargs)
        assert result == 42

    def test_parse_negative_number(self):
        """测试解析负数"""
        args = ()
        kwargs = {}
        result = ExpressionParser.parse("-10", args, kwargs)
        assert result == -10

    def test_parse_empty_expression_raises(self):
        """测试空表达式抛出异常"""
        with pytest.raises(ValueError, match="Expression cannot be empty"):
            ExpressionParser.parse("", (), {})

    def test_parse_invalid_expression_raises(self):
        """测试无效表达式抛出异常"""
        with pytest.raises(ValueError, match="Invalid expression"):
            ExpressionParser.parse("invalid!!!", (), {})

    def test_parse_private_attribute_raises(self):
        """测试访问私有属性抛出异常"""

        class Obj:
            def __init__(self):
                self._private = "secret"

        obj = Obj()
        args = (obj,)
        with pytest.raises(AttributeError, match="private attribute"):
            ExpressionParser.parse("#0._private", args, {})

    def test_parse_none_attribute_raises(self):
        """测试在 None 上访问属性抛出异常"""
        args = (None,)
        with pytest.raises(AttributeError, match="Cannot access attribute"):
            ExpressionParser.parse("#0.attr", args, {})


class TestCompiledExpression:
    """测试 CompiledExpression 类"""

    def test_compile_valid_expression(self):
        """测试编译有效表达式"""
        compiled = CompiledExpression("#user_id")
        assert compiled._expr == "#user_id"

    def test_compile_invalid_expression_raises(self):
        """测试编译无效表达式抛出异常"""
        with pytest.raises(ValueError, match="Invalid expression"):
            CompiledExpression("!!!invalid!!!")

    def test_evaluate_expression(self):
        """测试求值表达式"""
        compiled = CompiledExpression("#0.name")

        class User:
            def __init__(self):
                self.name = "Alice"

        user = User()
        result = compiled.evaluate((user,), {}, None)
        assert result == "Alice"

    def test_call_expression(self):
        """测试直接调用表达式"""
        compiled = CompiledExpression("#id")
        result = compiled(id=456)
        assert result == 456


class TestExpressionEvaluator:
    """测试 ExpressionEvaluator 类"""

    def test_evaluate(self):
        """测试求值"""
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate("#name", name="test")
        assert result == "test"

    def test_compile_and_cache(self):
        """测试编译并缓存"""
        evaluator = ExpressionEvaluator()
        compiled1 = evaluator.compile("#user.id")
        compiled2 = evaluator.compile("#user.id")
        # 应该返回同一个缓存对象
        assert compiled1 is compiled2

    def test_compile_different_expressions(self):
        """测试编译不同表达式"""
        evaluator = ExpressionEvaluator()
        compiled1 = evaluator.compile("#user.id")
        compiled2 = evaluator.compile("#feed.id")
        assert compiled1 is not compiled2
