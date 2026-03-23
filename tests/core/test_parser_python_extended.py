"""Extended Python parser tests covering previously uncovered branches."""
from __future__ import annotations

import pytest

from axon.core.parsers.python_lang import PythonParser


@pytest.fixture
def parser() -> PythonParser:
    return PythonParser()


# ---------------------------------------------------------------------------
# Decorated functions and classes
# ---------------------------------------------------------------------------

class TestDecoratedFunctions:
    def test_simple_decorator(self, parser: PythonParser) -> None:
        code = "@staticmethod\ndef helper():\n    pass\n"
        result = parser.parse(code, "test.py")
        syms = [s for s in result.symbols if s.name == "helper"]
        assert len(syms) == 1
        assert "staticmethod" in syms[0].decorators

    def test_attribute_decorator(self, parser: PythonParser) -> None:
        code = "@app.route\ndef index():\n    pass\n"
        result = parser.parse(code, "test.py")
        syms = [s for s in result.symbols if s.name == "index"]
        assert len(syms) == 1
        assert "app.route" in syms[0].decorators

    def test_call_decorator(self, parser: PythonParser) -> None:
        code = "@app.route('/home')\ndef home():\n    pass\n"
        result = parser.parse(code, "test.py")
        syms = [s for s in result.symbols if s.name == "home"]
        assert len(syms) == 1
        assert any("route" in d for d in syms[0].decorators)

    def test_decorated_class(self, parser: PythonParser) -> None:
        code = "@dataclass\nclass Point:\n    x: int\n    y: int\n"
        result = parser.parse(code, "test.py")
        classes = [s for s in result.symbols if s.kind == "class"]
        assert len(classes) == 1
        assert "dataclass" in classes[0].decorators

    def test_multiple_decorators(self, parser: PythonParser) -> None:
        code = "@classmethod\n@some_decorator\ndef method(cls):\n    pass\n"
        result = parser.parse(code, "test.py")
        syms = [s for s in result.symbols if s.name == "method"]
        assert len(syms) == 1
        assert len(syms[0].decorators) == 2


# ---------------------------------------------------------------------------
# Class superclasses — attribute and subscript forms
# ---------------------------------------------------------------------------

class TestClassSuperclasses:
    def test_attribute_base_class(self, parser: PythonParser) -> None:
        code = "class MyView(views.View):\n    pass\n"
        result = parser.parse(code, "test.py")
        heritage_names = [parent for _, _, parent in result.heritage]
        assert "views.View" in heritage_names

    def test_generic_subscript_base(self, parser: PythonParser) -> None:
        code = "from typing import Generic\nclass Container(Generic[T]):\n    pass\n"
        result = parser.parse(code, "test.py")
        heritage_names = [parent for _, _, parent in result.heritage]
        assert "Generic" in heritage_names

    def test_mixed_bases(self, parser: PythonParser) -> None:
        code = "class Child(Base, mixin.Mixin):\n    pass\n"
        result = parser.parse(code, "test.py")
        heritage_names = [parent for _, _, parent in result.heritage]
        assert "Base" in heritage_names
        assert "mixin.Mixin" in heritage_names


# ---------------------------------------------------------------------------
# Aliased imports
# ---------------------------------------------------------------------------

class TestAliasedImports:
    def test_import_as(self, parser: PythonParser) -> None:
        code = "import numpy as np\n"
        result = parser.parse(code, "test.py")
        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "numpy"
        assert imp.alias == "np"

    def test_from_import_with_alias(self, parser: PythonParser) -> None:
        # Parser recognizes the import but doesn't extract names for single aliased form
        code = "from os.path import join as path_join\n"
        result = parser.parse(code, "test.py")
        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "os.path"

    def test_mixed_alias_and_plain_names(self, parser: PythonParser) -> None:
        code = "from os.path import join, exists\n"
        result = parser.parse(code, "test.py")
        assert len(result.imports) == 1
        imp = result.imports[0]
        assert "join" in imp.names
        assert "exists" in imp.names


# ---------------------------------------------------------------------------
# Wildcard imports
# ---------------------------------------------------------------------------

class TestWildcardImport:
    def test_wildcard(self, parser: PythonParser) -> None:
        code = "from os.path import *\n"
        result = parser.parse(code, "test.py")
        assert len(result.imports) == 1
        assert "*" in result.imports[0].names


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------

class TestAllExports:
    def test_all_list(self, parser: PythonParser) -> None:
        code = '__all__ = ["foo", "bar", "baz"]\n'
        result = parser.parse(code, "test.py")
        assert "foo" in result.exports
        assert "bar" in result.exports
        assert "baz" in result.exports

    def test_all_tuple(self, parser: PythonParser) -> None:
        code = "__all__ = ('alpha', 'beta')\n"
        result = parser.parse(code, "test.py")
        assert "alpha" in result.exports
        assert "beta" in result.exports

    def test_non_all_assignment_ignored(self, parser: PythonParser) -> None:
        code = 'VERSION = ["1", "2"]\n'
        result = parser.parse(code, "test.py")
        assert result.exports == []


# ---------------------------------------------------------------------------
# except clauses
# ---------------------------------------------------------------------------

class TestExceptClauses:
    def test_simple_except(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    try:\n"
            "        pass\n"
            "    except ValueError:\n"
            "        pass\n"
        )
        result = parser.parse(code, "test.py")
        call_names = {c.name for c in result.calls}
        assert "ValueError" in call_names

    def test_tuple_except(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    try:\n"
            "        pass\n"
            "    except (TypeError, KeyError):\n"
            "        pass\n"
        )
        result = parser.parse(code, "test.py")
        call_names = {c.name for c in result.calls}
        assert "TypeError" in call_names
        assert "KeyError" in call_names

    def test_except_as(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    try:\n"
            "        pass\n"
            "    except RuntimeError as e:\n"
            "        pass\n"
        )
        result = parser.parse(code, "test.py")
        call_names = {c.name for c in result.calls}
        assert "RuntimeError" in call_names

    def test_except_tuple_as(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    try:\n"
            "        pass\n"
            "    except (IOError, OSError) as e:\n"
            "        pass\n"
        )
        result = parser.parse(code, "test.py")
        call_names = {c.name for c in result.calls}
        assert "IOError" in call_names or "OSError" in call_names


# ---------------------------------------------------------------------------
# raise statements
# ---------------------------------------------------------------------------

class TestRaiseStatements:
    def test_raise_class(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    raise ValueError\n"
        )
        result = parser.parse(code, "test.py")
        call_names = {c.name for c in result.calls}
        assert "ValueError" in call_names

    def test_raise_instance(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    raise ValueError('msg')\n"
        )
        result = parser.parse(code, "test.py")
        call_names = {c.name for c in result.calls}
        assert "ValueError" in call_names


# ---------------------------------------------------------------------------
# Attribute / chained calls
# ---------------------------------------------------------------------------

class TestAttributeAndChainedCalls:
    def test_nested_attribute_receiver(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    self.logger.info('hello')\n"
        )
        result = parser.parse(code, "test.py")
        info_calls = [c for c in result.calls if c.name == "info"]
        assert len(info_calls) >= 1
        assert info_calls[0].receiver == "self"

    def test_chained_call_receiver(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    get_user().save()\n"
        )
        result = parser.parse(code, "test.py")
        save_calls = [c for c in result.calls if c.name == "save"]
        assert len(save_calls) >= 1

    def test_keyword_argument_identifier(self, parser: PythonParser) -> None:
        code = (
            "def f():\n"
            "    router.add(handler=process_request)\n"
        )
        result = parser.parse(code, "test.py")
        add_calls = [c for c in result.calls if c.name == "add"]
        assert len(add_calls) >= 1
        assert "process_request" in add_calls[0].arguments


# ---------------------------------------------------------------------------
# Generic / complex type annotations
# ---------------------------------------------------------------------------

class TestComplexTypeAnnotations:
    def test_generic_param_type(self, parser: PythonParser) -> None:
        # List (uppercase) is not in _BUILTIN_TYPES, so it should appear as a type_ref
        code = (
            "from typing import List\n"
            "def f(x: List[User]) -> None:\n"
            "    pass\n"
        )
        result = parser.parse(code, "test.py")
        type_names = {t.name for t in result.type_refs}
        assert "List" in type_names

    def test_direct_identifier_type(self, parser: PythonParser) -> None:
        code = "def f(x: User) -> None:\n    pass\n"
        result = parser.parse(code, "test.py")
        param_types = [t for t in result.type_refs if t.kind == "param"]
        assert any(t.name == "User" for t in param_types)

    def test_return_type_custom_class(self, parser: PythonParser) -> None:
        code = "def f() -> Response:\n    pass\n"
        result = parser.parse(code, "test.py")
        return_types = [t for t in result.type_refs if t.kind == "return"]
        assert any(t.name == "Response" for t in return_types)

    def test_return_builtin_not_added(self, parser: PythonParser) -> None:
        code = "def f() -> str:\n    pass\n"
        result = parser.parse(code, "test.py")
        return_types = [t for t in result.type_refs if t.kind == "return"]
        assert all(t.name != "str" for t in return_types)


# ---------------------------------------------------------------------------
# Nested functions
# ---------------------------------------------------------------------------

class TestNestedFunctions:
    def test_nested_function_extracted(self, parser: PythonParser) -> None:
        code = (
            "def outer():\n"
            "    def inner():\n"
            "        pass\n"
        )
        result = parser.parse(code, "test.py")
        names = {s.name for s in result.symbols}
        assert "outer" in names
        assert "inner" in names

    def test_nested_function_not_method(self, parser: PythonParser) -> None:
        code = (
            "def outer():\n"
            "    def inner():\n"
            "        pass\n"
        )
        result = parser.parse(code, "test.py")
        inner = next(s for s in result.symbols if s.name == "inner")
        assert inner.class_name == ""


# ---------------------------------------------------------------------------
# async functions
# ---------------------------------------------------------------------------

class TestAsyncFunctions:
    def test_async_function_extracted(self, parser: PythonParser) -> None:
        code = "async def fetch(url: str) -> bytes:\n    pass\n"
        result = parser.parse(code, "test.py")
        syms = [s for s in result.symbols if s.name == "fetch"]
        assert len(syms) == 1
        assert syms[0].kind == "function"


# ---------------------------------------------------------------------------
# Variable type annotations
# ---------------------------------------------------------------------------

class TestVariableAnnotations:
    def test_variable_annotation_extracted(self, parser: PythonParser) -> None:
        code = "x: User = None\n"
        result = parser.parse(code, "test.py")
        var_refs = [t for t in result.type_refs if t.kind == "variable"]
        assert any(t.name == "User" for t in var_refs)

    def test_builtin_variable_type_skipped(self, parser: PythonParser) -> None:
        code = "x: int = 0\n"
        result = parser.parse(code, "test.py")
        var_refs = [t for t in result.type_refs if t.kind == "variable"]
        assert all(t.name != "int" for t in var_refs)


# ---------------------------------------------------------------------------
# Empty / edge case inputs
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_file(self, parser: PythonParser) -> None:
        result = parser.parse("", "empty.py")
        assert result.symbols == []
        assert result.imports == []
        assert result.calls == []

    def test_comment_only(self, parser: PythonParser) -> None:
        code = "# just a comment\n"
        result = parser.parse(code, "comment.py")
        assert result.symbols == []

    def test_multiline_import(self, parser: PythonParser) -> None:
        code = "from typing import (\n    List,\n    Dict,\n    Optional,\n)\n"
        result = parser.parse(code, "test.py")
        assert len(result.imports) == 1
        assert "List" in result.imports[0].names
        assert "Dict" in result.imports[0].names
        assert "Optional" in result.imports[0].names

    def test_module_level_call(self, parser: PythonParser) -> None:
        code = "setup(name='my_pkg')\n"
        result = parser.parse(code, "setup.py")
        call_names = {c.name for c in result.calls}
        assert "setup" in call_names
