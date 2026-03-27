---
status: complete
phase: 01-c-parser-foundation
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:30:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

## Current Test

[testing complete]

## Tests

### 1. C# Extension Registration
expected: Running `from axon.config.languages import get_language; print(get_language('Foo.cs'))` returns `"csharp"`. The `.cs` extension is recognized by the language detection layer.
result: pass

### 2. CSharpParser Import and Instantiation
expected: Running `from axon.core.parsers.csharp_lang import CSharpParser; p = CSharpParser()` completes without error. The parser module exists and can be instantiated.
result: pass

### 3. C# Symbol Extraction
expected: Parsing a `.cs` snippet containing a class and a method yields SymbolInfo objects with correct `name`, `kind` (`"class"` / `"method"`), and `class_name`. For example, parsing `class Foo { void Bar() {} }` produces at least `('Foo', 'class', '')` and `('Bar', 'method', 'Foo')`.
result: pass

### 4. Heritage Relationships
expected: A class with a base list like `class MyService : BaseService, IDisposable` produces heritage entries where `BaseService` is tagged as extends and `IDisposable` (I-prefix heuristic) is tagged as implements.
result: pass

### 5. Properties as Method Nodes
expected: A C# property declaration such as `public int Age { get; set; }` is emitted as a `kind="method"` SymbolInfo node with the enclosing class as `class_name`, not as a separate accessor pair.
result: pass

### 6. Namespace Metadata in Properties
expected: Symbols parsed from a file containing `namespace MyApp.Services { class Foo {} }` have `symbol.properties['cs_namespace'] == 'MyApp.Services'`. The namespace is stored in the `properties` dict and flows through to the graph node.
result: issue
reported: "Foo shows MyApp.Services but Bar (method) shows None — methods don't inherit cs_namespace from their enclosing namespace"
severity: major

### 7. Pipeline Registration
expected: `from axon.core.ingestion.parser_phase import get_parser; get_parser('csharp')` returns a `CSharpParser` instance without raising `ValueError`. The parser is registered in `_PARSER_FACTORIES`.
result: pass

### 8. All 29 C# Tests Pass
expected: Running `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py -q` reports **29 passed, 0 failed**. All six test classes (TestRegistration, TestImport, TestSymbolExtraction, TestImportResolution, TestHeritage, TestProperties, TestPipelineRegistration, TestQualifyCollisions) are green.
result: pass

### 9. No Regression on Existing Languages
expected: Running `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/ -q` shows all pre-existing tests still pass (698 tests collected, 0 failures). Python and TypeScript parsers are unaffected.
result: pass

## Summary

total: 9
passed: 8
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "All symbols (classes, methods, interfaces, enums) in a namespace block have cs_namespace set in their properties dict"
  status: failed
  reason: "User reported: methods don't inherit cs_namespace — only class nodes get it, method nodes show None"
  severity: major
  test: 6
  artifacts: [src/axon/core/parsers/csharp_lang.py]
  missing: ["cs_namespace propagation to method/property/constructor SymbolInfo nodes inside _extract_method, _extract_constructor, _extract_property"]
