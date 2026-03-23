"""Tests for the C# language parser.

Covers INFRA-01, INFRA-05, CS-01, CS-02, CS-03, CS-04.
Wave 0: stubs intentionally fail until Plan 02 implements CSharpParser.
"""

from __future__ import annotations

import pytest

# This import will fail (ModuleNotFoundError) until Plan 02 creates csharp_lang.py.
# That is intentional — these are the failing stubs.
from axon.core.parsers.csharp_lang import CSharpParser  # noqa: F401 (used in tests below)
from axon.config.languages import get_language
from axon.core.parsers.base import SymbolInfo


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
