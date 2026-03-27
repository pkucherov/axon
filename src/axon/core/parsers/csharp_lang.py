"""C# language parser using tree-sitter.

Extracts functions, methods, classes, interfaces, properties, and enums
from C# source code. Implements the LanguageParser protocol.

Limitations (Phase 1):
- Partial classes emit one node per file; Phase 5 handles merging.
- Heritage disambiguation uses I-prefix heuristic (no syntactic signal in grammar).
- Namespace-to-file import resolution is best-effort (see resolve_csharp_imports).
"""

from __future__ import annotations

import re

import tree_sitter_c_sharp as tscsharp
from tree_sitter import Language, Node, Parser

from axon.core.parsers.base import (
    ImportInfo,
    LanguageParser,
    ParseResult,
    SymbolInfo,
    TypeRef,
)

CS_LANGUAGE = Language(tscsharp.language())

_INTERFACE_RE = re.compile(r"^I[A-Z]")

_BUILTIN_TYPES: frozenset[str] = frozenset(
    {
        "bool",
        "byte",
        "sbyte",
        "char",
        "decimal",
        "double",
        "float",
        "int",
        "uint",
        "long",
        "ulong",
        "object",
        "short",
        "ushort",
        "string",
        "void",
        "dynamic",
        "Task",
        "IEnumerable",
        "IList",
        "ICollection",
        "IDictionary",
        "List",
        "Dictionary",
        "HashSet",
        "Queue",
        "Stack",
        "Array",
        "Nullable",
        "Func",
        "Action",
        "Predicate",
        "EventHandler",
        "Guid",
        "DateTime",
        "DateTimeOffset",
        "TimeSpan",
    }
)


class CSharpParser(LanguageParser):
    """Parses C# source code using tree-sitter."""

    def __init__(self) -> None:
        self._parser = Parser(CS_LANGUAGE)
        self._current_namespace: str = ""  # instance state reset per parse() call

    def parse(self, content: str, file_path: str) -> ParseResult:
        """Parse C# source and return structured information."""
        self._current_namespace = ""
        tree = self._parser.parse(bytes(content, "utf8"))
        result = ParseResult()

        # Pre-scan: detect file-scoped namespace (C# 10+) to set context before walking members
        for child in tree.root_node.children:
            if child.type == "file_scoped_namespace_declaration":
                self._current_namespace = self._get_namespace_name(child)
                break

        self._walk(tree.root_node, content, result, class_name="")
        return result

    def _walk(self, node: Node, content: str, result: ParseResult, class_name: str) -> None:
        """Recursively walk AST nodes and dispatch to extraction methods."""
        for child in node.children:
            match child.type:
                case "class_declaration" | "struct_declaration":
                    self._extract_class(child, content, result)
                case "interface_declaration":
                    self._extract_interface(child, content, result)
                case "method_declaration":
                    self._extract_method(child, content, result, class_name)
                case "constructor_declaration":
                    self._extract_constructor(child, content, result, class_name)
                case "property_declaration":
                    self._extract_property(child, content, result, class_name)
                case "enum_declaration":
                    self._extract_enum(child, content, result)
                case "namespace_declaration":
                    self._extract_namespace(child, content, result)
                case "file_scoped_namespace_declaration":
                    # Already handled by pre-scan in parse(); just walk the compilation_unit
                    pass
                case "using_directive":
                    self._extract_using(child, result)
                case "declaration_list":
                    self._walk(child, content, result, class_name)
                case _:
                    pass  # skip; do not recurse into unknown/block nodes

    def _extract_namespace(self, node: Node, content: str, result: ParseResult) -> None:
        """Extract block-style namespace name and recurse into its body."""
        ns_name = self._get_namespace_name(node)
        prev = self._current_namespace
        self._current_namespace = ns_name
        # Block-style namespace: walk its declaration_list body
        body = node.child_by_field_name("body")
        if body is not None:
            self._walk(body, content, result, class_name="")
        self._current_namespace = prev

    def _get_namespace_name(self, node: Node) -> str:
        """Extract the full namespace name string from a namespace declaration node."""
        for child in node.children:
            if child.type in ("qualified_name", "identifier"):
                return child.text.decode("utf8")
        return ""

    def _extract_class(self, node: Node, content: str, result: ParseResult) -> None:
        """Extract a class or struct declaration and its contents."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        class_name = name_node.text.decode("utf8")
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        node_content = content[node.start_byte : node.end_byte]

        # Detect partial modifier (D-09: emit one node per file; Phase 5 merges)
        is_partial = any(
            c.type == "modifier" and c.text.decode("utf8") == "partial" for c in node.children
        )

        # Extract attributes (D-08)
        attributes = self._extract_attributes(node)

        props: dict = {"cs_attributes": attributes}
        if self._current_namespace:
            props["cs_namespace"] = self._current_namespace
        if is_partial:
            props["cs_partial"] = True

        result.symbols.append(
            SymbolInfo(
                name=class_name,
                kind="class",
                start_line=start_line,
                end_line=end_line,
                content=node_content,
                properties=props,
            )
        )

        # Extract heritage: base_list is NOT a named field — iterate children
        for child in node.children:
            if child.type == "base_list":
                self._extract_heritage(class_name, child, result)

        # Walk body for methods, properties, nested classes
        body = node.child_by_field_name("body")
        if body is not None:
            self._walk(body, content, result, class_name=class_name)

    def _extract_interface(self, node: Node, content: str, result: ParseResult) -> None:
        """Extract an interface declaration and its members."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        interface_name = name_node.text.decode("utf8")
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        node_content = content[node.start_byte : node.end_byte]

        attributes = self._extract_attributes(node)
        props: dict = {"cs_attributes": attributes}
        if self._current_namespace:
            props["cs_namespace"] = self._current_namespace

        result.symbols.append(
            SymbolInfo(
                name=interface_name,
                kind="interface",
                start_line=start_line,
                end_line=end_line,
                content=node_content,
                properties=props,
            )
        )

        # Interface can extend other interfaces — extract heritage
        for child in node.children:
            if child.type == "base_list":
                self._extract_heritage(interface_name, child, result)

        # Walk interface body for method/property declarations
        body = node.child_by_field_name("body")
        if body is not None:
            self._walk(body, content, result, class_name=interface_name)

    def _extract_method(
        self, node: Node, content: str, result: ParseResult, class_name: str
    ) -> None:
        """Extract a method declaration."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        method_name = name_node.text.decode("utf8")
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        node_content = content[node.start_byte : node.end_byte]
        signature = self._build_method_signature(node)

        attributes = self._extract_attributes(node)
        props: dict = {}
        if attributes:
            props["cs_attributes"] = attributes
        if self._current_namespace:
            props["cs_namespace"] = self._current_namespace

        result.symbols.append(
            SymbolInfo(
                name=method_name,
                kind="method",
                start_line=start_line,
                end_line=end_line,
                content=node_content,
                signature=signature,
                class_name=class_name,
                properties=props,
            )
        )

        # Extract type refs from parameters
        self._extract_param_type_refs(node, result)

    def _extract_constructor(
        self, node: Node, content: str, result: ParseResult, class_name: str
    ) -> None:
        """Extract a constructor declaration as a method node."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        ctor_name = name_node.text.decode("utf8")
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        node_content = content[node.start_byte : node.end_byte]

        props: dict = {}
        if self._current_namespace:
            props["cs_namespace"] = self._current_namespace

        result.symbols.append(
            SymbolInfo(
                name=ctor_name,
                kind="method",
                start_line=start_line,
                end_line=end_line,
                content=node_content,
                class_name=class_name,
                properties=props,
            )
        )

    def _extract_property(
        self, node: Node, content: str, result: ParseResult, class_name: str
    ) -> None:
        """Extract a property declaration as a Method node (D-04).

        All property forms (auto {get;set;}, read-only {get;}, expression-bodied =>)
        produce one Method node each. No per-accessor nodes.
        """
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        prop_name = name_node.text.decode("utf8")
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        node_content = content[node.start_byte : node.end_byte]

        type_node = node.child_by_field_name("type")
        type_str = type_node.text.decode("utf8") if type_node else ""
        signature = f"{type_str} {prop_name}" if type_str else prop_name

        props: dict = {}
        if self._current_namespace:
            props["cs_namespace"] = self._current_namespace

        result.symbols.append(
            SymbolInfo(
                name=prop_name,
                kind="method",  # D-04: properties are Method nodes
                start_line=start_line,
                end_line=end_line,
                content=node_content,
                signature=signature,
                class_name=class_name,
                properties=props,
            )
        )

    def _extract_enum(self, node: Node, content: str, result: ParseResult) -> None:
        """Extract an enum declaration."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        enum_name = name_node.text.decode("utf8")
        props: dict = {}
        if self._current_namespace:
            props["cs_namespace"] = self._current_namespace

        result.symbols.append(
            SymbolInfo(
                name=enum_name,
                kind="enum",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                content=content[node.start_byte : node.end_byte],
                properties=props,
            )
        )

    def _extract_using(self, node: Node, result: ParseResult) -> None:
        """Extract a using directive — handles plain, static, and alias forms.

        Forms:
        - Plain:  ``using System.Collections;``             → module="System.Collections"
        - Static: ``using static System.Math;``             → module="System.Math"
        - Alias:  ``using MyAlias = Some.Namespace;``  → module="Some.Namespace", alias="MyAlias"
        """
        has_alias = any(c.type == "=" for c in node.children)
        alias_name = ""
        module = ""

        if has_alias:
            # Alias form: using MyAlias = Some.Namespace;
            # The 'name' field is the alias. Target is the qualified_name NOT the alias node.
            name_node = node.child_by_field_name("name")
            alias_name = name_node.text.decode("utf8") if name_node else ""
            # Filter out the alias node to get the actual target namespace/type
            targets = [
                c
                for c in node.children
                if c.type in ("qualified_name", "identifier") and c is not name_node
            ]
            module = targets[0].text.decode("utf8") if targets else ""
        else:
            # Plain or static using: take first qualified_name or identifier
            for c in node.children:
                if c.type in ("qualified_name", "identifier"):
                    module = c.text.decode("utf8")
                    break

        if module:
            result.imports.append(
                ImportInfo(
                    module=module,
                    names=[],
                    alias=alias_name,
                )
            )

    def _extract_heritage(
        self, class_name: str, base_list_node: Node, result: ParseResult
    ) -> None:
        """Extract heritage tuples from a base_list node.

        Uses I-prefix heuristic to distinguish implements from extends:
        names starting with uppercase I followed by another uppercase letter
        are conventionally interfaces. Everything else is treated as extends.
        """
        for child in base_list_node.children:
            if child.type == "identifier":
                parent_name = child.text.decode("utf8")
            elif child.type == "generic_name":
                # Generic base like List<T> or IList<T>
                id_node = child.children[0] if child.children else None
                if id_node is None:
                    continue
                parent_name = id_node.text.decode("utf8")
            else:
                continue  # skip ':' and ',' separators

            kind = "implements" if _INTERFACE_RE.match(parent_name) else "extends"
            result.heritage.append((class_name, kind, parent_name))

    def _extract_attributes(self, decl_node: Node) -> list[str]:
        """Extract C# attribute names from a declaration node's attribute_list children.

        attribute_list nodes appear as unnamed direct children of declaration nodes.
        Each attribute_list contains one or more attribute children.
        """
        attrs: list[str] = []
        for child in decl_node.children:
            if child.type == "attribute_list":
                for sub in child.children:
                    if sub.type == "attribute":
                        # First child of attribute is the identifier (name)
                        if sub.children:
                            attrs.append(sub.children[0].text.decode("utf8"))
        return attrs

    def _build_method_signature(self, method_node: Node) -> str:
        """Build a human-readable signature string for a method."""
        name_node = method_node.child_by_field_name("name")
        params_node = method_node.child_by_field_name("parameters")
        returns_node = method_node.child_by_field_name("returns")

        if name_node is None or params_node is None:
            return ""

        name = name_node.text.decode("utf8")
        params = params_node.text.decode("utf8")
        return_type = returns_node.text.decode("utf8") if returns_node else "void"
        return f"{return_type} {name}{params}"

    def _extract_param_type_refs(self, method_node: Node, result: ParseResult) -> None:
        """Extract type references from method parameters."""
        params_node = method_node.child_by_field_name("parameters")
        if params_node is None:
            return

        for child in params_node.children:
            if child.type != "parameter":
                continue
            type_node = child.child_by_field_name("type")
            name_node = child.child_by_field_name("name")
            if type_node is None or name_node is None:
                continue

            # Extract the base type name (strip generics)
            if type_node.type == "identifier":
                type_name = type_node.text.decode("utf8")
            elif type_node.type == "generic_name":
                type_name = (
                    type_node.children[0].text.decode("utf8") if type_node.children else ""
                )
            elif type_node.type == "predefined_type":
                type_name = type_node.text.decode("utf8")  # will be in _BUILTIN_TYPES
            else:
                type_name = ""

            if type_name and type_name not in _BUILTIN_TYPES:
                result.type_refs.append(
                    TypeRef(
                        name=type_name,
                        kind="param",
                        line=type_node.start_point[0] + 1,
                        param_name=name_node.text.decode("utf8"),
                    )
                )


def resolve_csharp_imports(all_parse_data: list) -> None:
    """Second pass: resolve 'using' namespace strings to file paths.

    Builds a map of {namespace_string: file_path} from all parsed .cs files,
    then patches ImportInfo.module to a file path where resolvable.
    Unresolved namespaces remain as-is (no IMPORTS edge will be created
    downstream for unresolved modules).

    Args:
        all_parse_data: List of FileParseData from parser_phase.process_parsing.
            Uses duck-typing: each entry must have .language, .file_path, .parse_result.
    """
    # Step 1: Build namespace -> file_path map from all C# symbols
    ns_to_file: dict[str, str] = {}
    for pd in all_parse_data:
        if pd.language != "csharp":
            continue
        for sym in pd.parse_result.symbols:
            ns = (sym.properties or {}).get("cs_namespace", "")
            if ns and ns not in ns_to_file:
                ns_to_file[ns] = pd.file_path

    # Step 2: Patch matching imports to file paths
    for pd in all_parse_data:
        if pd.language != "csharp":
            continue
        for imp in pd.parse_result.imports:
            resolved = ns_to_file.get(imp.module)
            if resolved:
                imp.module = resolved
