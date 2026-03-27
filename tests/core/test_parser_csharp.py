"""Tests for the C# language parser.

Covers INFRA-01, INFRA-05, CS-01, CS-02, CS-03, CS-04.
Wave 0: stubs intentionally fail until Plan 02 implements CSharpParser.
Plan 03: adds pipeline integration tests (CS-02 import resolution, D-05 collision detection).
"""

from __future__ import annotations

import pytest

from axon.config.languages import get_language

# This import will fail (ModuleNotFoundError) until Plan 02 creates csharp_lang.py.
# That is intentional — these are the failing stubs.
from axon.core.parsers.base import SymbolInfo
from axon.core.parsers.csharp_lang import CSharpParser  # noqa: F401 (used in tests below)

# ── INFRA-01 ────────────────────────────────────────────────────────────────


class TestRegistration:
    def test_cs_extension_maps_to_csharp(self):
        """INFRA-01: .cs files must resolve to the 'csharp' language key."""
        assert get_language("MyScript.cs") == "csharp"

    def test_cs_extension_case_insensitive_path(self):
        """.cs suffix recognized regardless of parent path."""
        assert get_language("/some/path/Foo.cs") == "csharp"

    def test_non_cs_extensions_unaffected(self):
        """Existing language detection is not broken."""
        assert get_language("foo.py") == "python"
        assert get_language("bar.ts") == "typescript"
        assert get_language("baz.js") == "javascript"


# ── INFRA-05 ────────────────────────────────────────────────────────────────


class TestImport:
    def test_tree_sitter_csharp_importable(self):
        """INFRA-05: tree-sitter-c-sharp package must be importable."""
        import tree_sitter_c_sharp as tscsharp  # noqa: F401

        assert callable(tscsharp.language)

    def test_csharp_parser_instantiates(self):
        """INFRA-05: CSharpParser must instantiate without error."""
        parser = CSharpParser()
        assert parser is not None


# ── CS-01 ────────────────────────────────────────────────────────────────────

_SIMPLE_CLASS = """\
namespace MyApp;

public class MyService
{
    public void DoWork() { }
    public static int Compute(int x) { return x; }
}
"""

_INTERFACE_CS = """\
namespace MyApp;

public interface IRepository
{
    void Save();
    int Count { get; }
}
"""


class TestSymbolExtraction:
    def test_class_node_extracted(self):
        """CS-01: Class declaration produces a SymbolInfo with kind='class'."""
        parser = CSharpParser()
        result = parser.parse(_SIMPLE_CLASS, "MyService.cs")
        classes = [s for s in result.symbols if s.kind == "class"]
        assert any(c.name == "MyService" for c in classes)

    def test_method_node_extracted(self):
        """CS-01: Method declarations produce SymbolInfo with kind='method'."""
        parser = CSharpParser()
        result = parser.parse(_SIMPLE_CLASS, "MyService.cs")
        methods = [s for s in result.symbols if s.kind == "method"]
        assert any(m.name == "DoWork" for m in methods)
        assert any(m.name == "Compute" for m in methods)

    def test_method_has_class_name(self):
        """CS-01: Method nodes carry their owning class name."""
        parser = CSharpParser()
        result = parser.parse(_SIMPLE_CLASS, "MyService.cs")
        do_work = next(s for s in result.symbols if s.name == "DoWork")
        assert do_work.class_name == "MyService"

    def test_interface_node_extracted(self):
        """CS-01: Interface declarations produce SymbolInfo with kind='interface'."""
        parser = CSharpParser()
        result = parser.parse(_INTERFACE_CS, "IRepository.cs")
        interfaces = [s for s in result.symbols if s.kind == "interface"]
        assert any(i.name == "IRepository" for i in interfaces)

    def test_namespace_stored_in_properties(self):
        """D-06: Namespace is always stored in properties['cs_namespace']."""
        parser = CSharpParser()
        result = parser.parse(_SIMPLE_CLASS, "MyService.cs")
        cls = next(s for s in result.symbols if s.name == "MyService")
        assert cls.properties.get("cs_namespace") == "MyApp"


# ── CS-02 ────────────────────────────────────────────────────────────────────

_USING_CS = """\
using System;
using static System.Math;
using MyAlias = System.Collections.Generic.List<int>;
using System.Collections.Generic;

namespace MyApp;

public class Foo { }
"""


class TestImportResolution:
    def test_plain_using_extracted(self):
        """CS-02: Plain `using Namespace;` produces an ImportInfo."""
        parser = CSharpParser()
        result = parser.parse(_USING_CS, "Foo.cs")
        modules = [imp.module for imp in result.imports]
        assert "System" in modules

    def test_static_using_extracted(self):
        """CS-02: `using static Type;` produces an ImportInfo with the type path."""
        parser = CSharpParser()
        result = parser.parse(_USING_CS, "Foo.cs")
        modules = [imp.module for imp in result.imports]
        assert "System.Math" in modules

    def test_alias_using_extracted_with_target(self):
        """CS-02: Alias `using X = Y;` produces ImportInfo with module=Y (the target)."""
        parser = CSharpParser()
        result = parser.parse(_USING_CS, "Foo.cs")
        # Target namespace/type, NOT the alias 'MyAlias'
        modules = [imp.module for imp in result.imports]
        assert any("List" in m or "Generic" in m for m in modules)

    def test_qualified_using_extracted(self):
        """CS-02: `using System.Collections.Generic;` extracted correctly."""
        parser = CSharpParser()
        result = parser.parse(_USING_CS, "Foo.cs")
        modules = [imp.module for imp in result.imports]
        assert "System.Collections.Generic" in modules


# ── CS-03 ────────────────────────────────────────────────────────────────────

_HERITAGE_CS = """\
namespace MyApp;

public class Animal { }
public class Dog : Animal { }
public class Cat : Animal, IDisposable { }
public interface IDisposable { }
"""


class TestHeritage:
    def test_extends_edge_from_single_parent(self):
        """CS-03: Single base class produces an EXTENDS heritage tuple."""
        parser = CSharpParser()
        result = parser.parse(_HERITAGE_CS, "Animals.cs")
        extends = [(c, p) for c, k, p in result.heritage if k == "extends"]
        assert ("Dog", "Animal") in extends

    def test_extends_and_implements_distinguished(self):
        """CS-03: I-prefix heuristic distinguishes implements from extends."""
        parser = CSharpParser()
        result = parser.parse(_HERITAGE_CS, "Animals.cs")
        implements = [(c, p) for c, k, p in result.heritage if k == "implements"]
        extends = [(c, p) for c, k, p in result.heritage if k == "extends"]
        assert ("Cat", "IDisposable") in implements
        assert ("Cat", "Animal") in extends

    def test_interface_heritage_from_interface_declaration(self):
        """CS-03: Interface can also extend another interface."""
        cs = "namespace X;\npublic interface IFoo : IBar { }"
        parser = CSharpParser()
        result = parser.parse(cs, "IFoo.cs")
        implements = [(c, p) for c, k, p in result.heritage if k == "implements"]
        assert ("IFoo", "IBar") in implements


# ── CS-04 ────────────────────────────────────────────────────────────────────

_PROPERTY_CS = """\
namespace MyApp;

public class Entity
{
    public int Id { get; set; }
    public string Name { get; }
    public bool IsActive => true;
}
"""


class TestProperties:
    def test_auto_property_as_method_node(self):
        """CS-04: Auto property {get;set;} produces a SymbolInfo with kind='method'."""
        parser = CSharpParser()
        result = parser.parse(_PROPERTY_CS, "Entity.cs")
        props = [s for s in result.symbols if s.kind == "method" and s.name == "Id"]
        assert len(props) == 1

    def test_readonly_property_as_method_node(self):
        """CS-04: Readonly property {get;} produces a SymbolInfo with kind='method'."""
        parser = CSharpParser()
        result = parser.parse(_PROPERTY_CS, "Entity.cs")
        props = [s for s in result.symbols if s.kind == "method" and s.name == "Name"]
        assert len(props) == 1

    def test_expression_bodied_property_as_method_node(self):
        """CS-04: Expression-bodied property => produces a SymbolInfo with kind='method'."""
        parser = CSharpParser()
        result = parser.parse(_PROPERTY_CS, "Entity.cs")
        props = [s for s in result.symbols if s.kind == "method" and s.name == "IsActive"]
        assert len(props) == 1

    def test_property_has_class_name(self):
        """CS-04: Property node carries the owning class name."""
        parser = CSharpParser()
        result = parser.parse(_PROPERTY_CS, "Entity.cs")
        id_prop = next(s for s in result.symbols if s.name == "Id" and s.kind == "method")
        assert id_prop.class_name == "Entity"


# ── Pipeline Integration (Plan 03) ──────────────────────────────────────────


class TestPipelineRegistration:
    def test_csharp_in_parser_factories(self):
        """get_parser('csharp') must return a CSharpParser without ValueError."""
        from axon.core.ingestion.parser_phase import get_parser

        parser = get_parser("csharp")
        assert isinstance(parser, CSharpParser)

    def test_parser_factories_key_exists(self):
        """_PARSER_FACTORIES dict must contain 'csharp' key."""
        from axon.core.ingestion.parser_phase import _PARSER_FACTORIES

        assert "csharp" in _PARSER_FACTORIES

    def test_get_parser_error_message_includes_csharp(self):
        """ValueError for unknown language should mention 'csharp' in supported list."""
        from axon.core.ingestion.parser_phase import get_parser

        with pytest.raises(ValueError, match="csharp"):
            get_parser("cobol")


class TestQualifyCollisions:
    def test_qualify_collisions_empty_list(self):
        """_qualify_collisions must run without error on empty list."""
        from axon.core.ingestion.parser_phase import _qualify_collisions

        _qualify_collisions([])  # should not raise

    def test_qualify_collisions_single_csharp_file_no_rename(self):
        """If only one C# file defines 'Foo', the name is not qualified."""
        from axon.core.ingestion.parser_phase import _qualify_collisions
        from axon.core.parsers.base import ParseResult

        sym = SymbolInfo(
            name="Foo",
            kind="class",
            start_line=1,
            end_line=5,
            content="class Foo {}",
            properties={"cs_namespace": "MyApp"},
        )
        pr = ParseResult()
        pr.symbols.append(sym)

        class FakePD:
            language = "csharp"
            parse_result = pr

        _qualify_collisions([FakePD()])
        assert sym.name == "Foo"  # unchanged — no collision

    def test_qualify_collisions_two_files_same_name_get_qualified(self):
        """Two C# files both defining 'Foo' must result in qualified names."""
        from axon.core.ingestion.parser_phase import _qualify_collisions
        from axon.core.parsers.base import ParseResult

        sym1 = SymbolInfo(
            name="Foo",
            kind="class",
            start_line=1,
            end_line=5,
            content="class Foo {}",
            properties={"cs_namespace": "MyApp"},
        )
        sym2 = SymbolInfo(
            name="Foo",
            kind="class",
            start_line=1,
            end_line=5,
            content="class Foo {}",
            properties={"cs_namespace": "OtherApp"},
        )
        pr1, pr2 = ParseResult(), ParseResult()
        pr1.symbols.append(sym1)
        pr2.symbols.append(sym2)

        class FakePD:
            def __init__(self, pr: ParseResult) -> None:
                self.language = "csharp"
                self.parse_result = pr

        _qualify_collisions([FakePD(pr1), FakePD(pr2)])
        assert sym1.name == "MyApp.Foo"
        assert sym2.name == "OtherApp.Foo"

    def test_qualify_collisions_non_csharp_files_unaffected(self):
        """Python/TS files must not be touched by collision detection."""
        from axon.core.ingestion.parser_phase import _qualify_collisions
        from axon.core.parsers.base import ParseResult

        sym = SymbolInfo(
            name="Foo",
            kind="class",
            start_line=1,
            end_line=5,
            content="class Foo: pass",
        )
        pr = ParseResult()
        pr.symbols.append(sym)

        class FakePD:
            language = "python"
            parse_result = pr

        _qualify_collisions([FakePD()])
        assert sym.name == "Foo"  # non-C# symbol untouched

    def test_qualify_collisions_only_class_and_interface_kinds(self):
        """Only 'class' and 'interface' symbols are subject to collision detection."""
        from axon.core.ingestion.parser_phase import _qualify_collisions
        from axon.core.parsers.base import ParseResult

        method1 = SymbolInfo(
            name="DoWork",
            kind="method",
            start_line=1,
            end_line=3,
            content="void DoWork() {}",
            properties={"cs_namespace": "A"},
        )
        method2 = SymbolInfo(
            name="DoWork",
            kind="method",
            start_line=1,
            end_line=3,
            content="void DoWork() {}",
            properties={"cs_namespace": "B"},
        )
        pr1, pr2 = ParseResult(), ParseResult()
        pr1.symbols.append(method1)
        pr2.symbols.append(method2)

        class FakePD:
            def __init__(self, pr: ParseResult) -> None:
                self.language = "csharp"
                self.parse_result = pr

        _qualify_collisions([FakePD(pr1), FakePD(pr2)])
        # Methods with same name should NOT be renamed
        assert method1.name == "DoWork"
        assert method2.name == "DoWork"


# ── Namespace Propagation on Method/Constructor/Property (Plan 04 gap closure) ──


_NS_BLOCK_CS = """\
namespace MyApp.Services
{
    class Foo
    {
        void Bar() { }
        Foo() { }
        public int Age { get; set; }
    }
}
"""

_NO_NS_CS = """\
class Bare
{
    void Run() { }
    Bare() { }
    public string Label { get; }
}
"""


class TestNamespacePropagation:
    def test_method_inside_namespace_has_cs_namespace(self):
        """Plan 04 gap #6: method nodes inside a namespace block carry cs_namespace."""
        parser = CSharpParser()
        result = parser.parse(_NS_BLOCK_CS, "Foo.cs")
        bar = next((s for s in result.symbols if s.name == "Bar" and s.kind == "method"), None)
        assert bar is not None, "Method 'Bar' not found in symbols"
        assert bar.properties.get("cs_namespace") == "MyApp.Services"

    def test_constructor_inside_namespace_has_cs_namespace(self):
        """Plan 04 gap #6: constructor nodes inside a namespace block carry cs_namespace."""
        parser = CSharpParser()
        result = parser.parse(_NS_BLOCK_CS, "Foo.cs")
        ctor = next(
            (
                s
                for s in result.symbols
                if s.name == "Foo" and s.kind == "method" and s.class_name == "Foo"
            ),
            None,
        )
        assert ctor is not None, "Constructor 'Foo' not found in symbols"
        assert ctor.properties.get("cs_namespace") == "MyApp.Services"

    def test_property_inside_namespace_has_cs_namespace(self):
        """Plan 04 gap #6: property nodes inside a namespace block carry cs_namespace."""
        parser = CSharpParser()
        result = parser.parse(_NS_BLOCK_CS, "Foo.cs")
        age = next((s for s in result.symbols if s.name == "Age" and s.kind == "method"), None)
        assert age is not None, "Property 'Age' not found in symbols"
        assert age.properties.get("cs_namespace") == "MyApp.Services"

    def test_method_outside_namespace_has_no_cs_namespace(self):
        """No regression: methods outside any namespace have no cs_namespace key."""
        parser = CSharpParser()
        result = parser.parse(_NO_NS_CS, "Bare.cs")
        run = next((s for s in result.symbols if s.name == "Run" and s.kind == "method"), None)
        assert run is not None, "Method 'Run' not found in symbols"
        assert "cs_namespace" not in run.properties

    def test_class_inside_namespace_still_has_cs_namespace(self):
        """No regression: class nodes inside a namespace block still carry cs_namespace."""
        parser = CSharpParser()
        result = parser.parse(_NS_BLOCK_CS, "Foo.cs")
        foo_cls = next((s for s in result.symbols if s.name == "Foo" and s.kind == "class"), None)
        assert foo_cls is not None, "Class 'Foo' not found in symbols"
        assert foo_cls.properties.get("cs_namespace") == "MyApp.Services"
