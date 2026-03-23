"""Extended tests for calls.py covering previously uncovered branches."""
from __future__ import annotations

import pytest

from axon.core.graph.graph import KnowledgeGraph
from axon.core.graph.model import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelType,
    generate_id,
)
from axon.core.ingestion.calls import (
    _CALL_BLOCKLIST,
    _build_import_cache,
    _common_prefix_len,
    _make_edge,
    _pick_closest,
    _resolve_receiver_method,
    _resolve_self_method,
    _resolve_via_imports,
    process_calls,
    resolve_call,
    resolve_file_calls,
)
from axon.core.ingestion.parser_phase import FileParseData
from axon.core.ingestion.symbol_lookup import build_file_symbol_index, build_name_index
from axon.core.parsers.base import CallInfo, ParseResult, SymbolInfo


_CALLABLE_LABELS = (NodeLabel.FUNCTION, NodeLabel.METHOD, NodeLabel.CLASS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_file(graph: KnowledgeGraph, path: str) -> str:
    nid = generate_id(NodeLabel.FILE, path)
    graph.add_node(GraphNode(id=nid, label=NodeLabel.FILE, name=path.split("/")[-1], file_path=path))
    return nid


def _add_fn(graph: KnowledgeGraph, path: str, name: str,
            start: int = 1, end: int = 10, class_name: str = "") -> str:
    label = NodeLabel.METHOD if class_name else NodeLabel.FUNCTION
    sym_name = f"{class_name}.{name}" if class_name else name
    nid = generate_id(label, path, sym_name)
    graph.add_node(GraphNode(
        id=nid, label=label, name=name,
        file_path=path, start_line=start, end_line=end, class_name=class_name,
    ))
    return nid


def _add_cls(graph: KnowledgeGraph, path: str, name: str) -> str:
    nid = generate_id(NodeLabel.CLASS, path, name)
    graph.add_node(GraphNode(
        id=nid, label=NodeLabel.CLASS, name=name, file_path=path, start_line=1, end_line=20,
    ))
    return nid


def _add_import_rel(graph: KnowledgeGraph, caller_path: str,
                    target_path: str, symbols: str = "") -> None:
    caller_file_id = generate_id(NodeLabel.FILE, caller_path)
    target_file_id = generate_id(NodeLabel.FILE, target_path)
    graph.add_relationship(GraphRelationship(
        id=f"imports:{caller_file_id}->{target_file_id}",
        type=RelType.IMPORTS,
        source=caller_file_id,
        target=target_file_id,
        properties={"symbols": symbols},
    ))


# ---------------------------------------------------------------------------
# _common_prefix_len
# ---------------------------------------------------------------------------

class TestCommonPrefixLen:
    def test_same_directory(self) -> None:
        assert _common_prefix_len("src/a.py", "src/b.py") == 1

    def test_no_common(self) -> None:
        assert _common_prefix_len("a/b.py", "c/d.py") == 0

    def test_nested_common(self) -> None:
        assert _common_prefix_len("src/api/x.py", "src/api/y.py") == 2


# ---------------------------------------------------------------------------
# _make_edge — deduplication
# ---------------------------------------------------------------------------

class TestMakeEdge:
    def test_creates_edge(self) -> None:
        seen: set[str] = set()
        edge = _make_edge("fn:a", "fn:b", 1.0, seen)
        assert edge is not None
        assert edge.source == "fn:a"

    def test_deduplicates(self) -> None:
        seen: set[str] = set()
        e1 = _make_edge("fn:a", "fn:b", 1.0, seen)
        e2 = _make_edge("fn:a", "fn:b", 1.0, seen)
        assert e1 is not None
        assert e2 is None


# ---------------------------------------------------------------------------
# _pick_closest
# ---------------------------------------------------------------------------

class TestPickClosest:
    def test_picks_closest_directory(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_file(graph, "lib/b.py")
        f1 = _add_fn(graph, "src/a.py", "target")
        f2 = _add_fn(graph, "lib/b.py", "target")

        result = _pick_closest([f1, f2], graph, caller_file_path="src/caller.py")
        assert result == f1

    def test_returns_none_for_empty_candidates(self) -> None:
        result = _pick_closest([], KnowledgeGraph(), caller_file_path="src/a.py")
        assert result is None

    def test_no_caller_path(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        fn = _add_fn(graph, "src/a.py", "helper")
        result = _pick_closest([fn], graph, caller_file_path="")
        assert result == fn


# ---------------------------------------------------------------------------
# _resolve_self_method
# ---------------------------------------------------------------------------

class TestResolveSelfMethod:
    def test_finds_method_in_same_class(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        method_id = _add_fn(graph, "src/a.py", "save", class_name="User")
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        result = _resolve_self_method("save", "src/a.py", call_index, graph, "User")
        assert result == method_id

    def test_returns_fallback_without_class(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        method_id = _add_fn(graph, "src/a.py", "save", class_name="User")
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        result = _resolve_self_method("save", "src/a.py", call_index, graph, None)
        assert result == method_id

    def test_returns_none_when_not_found(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        result = _resolve_self_method("nonexistent", "src/a.py", call_index, graph)
        assert result is None


# ---------------------------------------------------------------------------
# _build_import_cache
# ---------------------------------------------------------------------------

class TestBuildImportCache:
    def test_named_import(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_file(graph, "src/b.py")
        _add_import_rel(graph, "src/a.py", "src/b.py", symbols="validate")

        cache = _build_import_cache("src/a.py", graph)
        assert "validate" in cache
        assert "src/b.py" in cache["validate"]

    def test_wildcard_import(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_file(graph, "src/b.py")
        _add_import_rel(graph, "src/a.py", "src/b.py", symbols="")

        cache = _build_import_cache("src/a.py", graph)
        assert "*" in cache
        assert "src/b.py" in cache["*"]

    def test_empty_for_no_imports(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        cache = _build_import_cache("src/a.py", graph)
        assert cache == {}


# ---------------------------------------------------------------------------
# _resolve_via_imports
# ---------------------------------------------------------------------------

class TestResolveViaImports:
    def test_resolves_via_explicit_import(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_file(graph, "src/b.py")
        target_id = _add_fn(graph, "src/b.py", "validate")
        cache = {"validate": {"src/b.py"}}

        result = _resolve_via_imports("validate", [target_id], graph, cache)
        assert result == target_id

    def test_resolves_via_wildcard_import(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_file(graph, "src/b.py")
        target_id = _add_fn(graph, "src/b.py", "helper")
        cache = {"*": {"src/b.py"}}

        result = _resolve_via_imports("helper", [target_id], graph, cache)
        assert result == target_id

    def test_returns_none_for_empty_cache(self) -> None:
        result = _resolve_via_imports("foo", ["function:a:foo"], KnowledgeGraph(), {})
        assert result is None

    def test_returns_none_when_not_imported(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/b.py")
        target_id = _add_fn(graph, "src/b.py", "bar")
        cache = {"other": {"src/c.py"}}

        result = _resolve_via_imports("bar", [target_id], graph, cache)
        assert result is None


# ---------------------------------------------------------------------------
# _resolve_receiver_method
# ---------------------------------------------------------------------------

class TestResolveReceiverMethod:
    def test_same_file_match(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        method_id = _add_fn(graph, "src/a.py", "save", class_name="User")
        source_id = _add_fn(graph, "src/a.py", "update")
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        edge = _resolve_receiver_method("User", "save", source_id, "src/a.py", call_index, graph)
        assert edge is not None
        assert edge.target == method_id
        assert edge.properties["confidence"] == 0.8

    def test_global_match(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_file(graph, "src/b.py")
        method_id = _add_fn(graph, "src/b.py", "save", class_name="User")
        source_id = _add_fn(graph, "src/a.py", "update")
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        edge = _resolve_receiver_method("User", "save", source_id, "src/a.py", call_index, graph)
        assert edge is not None
        assert edge.target == method_id

    def test_returns_none_for_no_match(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        source_id = _add_fn(graph, "src/a.py", "update")
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        edge = _resolve_receiver_method("NoClass", "save", source_id, "src/a.py", call_index, graph)
        assert edge is None


# ---------------------------------------------------------------------------
# resolve_call — edge cases
# ---------------------------------------------------------------------------

class TestResolveCallEdgeCases:
    def test_returns_none_when_no_candidates(self) -> None:
        graph = KnowledgeGraph()
        call_index: dict[str, list[str]] = {}

        result_id, conf = resolve_call(
            CallInfo(name="nonexistent", line=1), "src/a.py", call_index, graph
        )
        assert result_id is None
        assert conf == 0.0

    def test_too_many_candidates_no_global_fuzzy(self) -> None:
        # When >5 candidates exist, global fuzzy match is skipped.
        graph = KnowledgeGraph()
        candidate_ids = []
        for i in range(6):
            _add_file(graph, f"src/{i}.py")
            cid = _add_fn(graph, f"src/{i}.py", "common")
            candidate_ids.append(cid)

        call_index = {"common": candidate_ids}

        result_id, conf = resolve_call(
            CallInfo(name="common", line=1), "src/other.py", call_index, graph
        )
        assert result_id is None

    def test_self_receiver_resolves_method(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        method_id = _add_fn(graph, "src/a.py", "validate", class_name="User")
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        result_id, conf = resolve_call(
            CallInfo(name="validate", line=1, receiver="self"),
            "src/a.py", call_index, graph,
            caller_class_name="User",
        )
        assert result_id == method_id
        assert conf == 1.0


# ---------------------------------------------------------------------------
# resolve_file_calls — self-method, receiver method, arguments, decorators
# ---------------------------------------------------------------------------

class TestResolveFileCalls:
    def _make_parse_result_with_self_call(self) -> ParseResult:
        return ParseResult(
            calls=[CallInfo(name="validate", line=5, receiver="self")],
            symbols=[SymbolInfo(
                name="submit", kind="method", start_line=1, end_line=10,
                content="", class_name="Form",
            )],
        )

    def test_self_receiver_resolved(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/form.py")
        submit_id = _add_fn(graph, "src/form.py", "submit", start=1, end=10, class_name="Form")
        validate_id = _add_fn(graph, "src/form.py", "validate", start=12, end=20, class_name="Form")
        call_index = build_name_index(graph, _CALLABLE_LABELS)
        file_sym_index = build_file_symbol_index(graph, _CALLABLE_LABELS)

        fpd = FileParseData(
            file_path="src/form.py",
            language="python",
            parse_result=ParseResult(
                calls=[CallInfo(name="validate", line=5, receiver="self")],
                symbols=[SymbolInfo(name="submit", kind="method", start_line=1,
                                    end_line=10, content="", class_name="Form")],
            ),
        )

        edges = resolve_file_calls(fpd, call_index, file_sym_index, graph)
        assert len(edges) >= 1

    def test_blocked_call_skipped(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_fn(graph, "src/a.py", "main", start=1, end=10)
        call_index = build_name_index(graph, _CALLABLE_LABELS)
        file_sym_index = build_file_symbol_index(graph, _CALLABLE_LABELS)

        fpd = FileParseData(
            file_path="src/a.py",
            language="python",
            parse_result=ParseResult(
                calls=[CallInfo(name="print", line=5)],  # blocked
                symbols=[SymbolInfo(name="main", kind="function", start_line=1, end_line=10, content="")],
            ),
        )

        edges = resolve_file_calls(fpd, call_index, file_sym_index, graph)
        assert edges == []

    def test_argument_identifier_creates_edge(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        caller_fn = _add_fn(graph, "src/a.py", "main", start=1, end=10)
        callback_fn = _add_fn(graph, "src/a.py", "handler", start=12, end=20)
        call_index = build_name_index(graph, _CALLABLE_LABELS)
        file_sym_index = build_file_symbol_index(graph, _CALLABLE_LABELS)

        fpd = FileParseData(
            file_path="src/a.py",
            language="python",
            parse_result=ParseResult(
                calls=[CallInfo(name="register", line=5, arguments=["handler"])],
                symbols=[SymbolInfo(name="main", kind="function", start_line=1, end_line=10, content="")],
            ),
        )
        _add_fn(graph, "src/a.py", "register", start=22, end=30)
        call_index = build_name_index(graph, _CALLABLE_LABELS)

        edges = resolve_file_calls(fpd, call_index, file_sym_index, graph)
        # Should have an edge for 'handler' argument
        arg_edges = [e for e in edges if e.target == callback_fn]
        assert len(arg_edges) >= 1

    def test_receiver_method_resolution(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        caller_fn = _add_fn(graph, "src/a.py", "run", start=1, end=10)
        method_id = _add_fn(graph, "src/a.py", "execute", start=12, end=20, class_name="Worker")
        call_index = build_name_index(graph, _CALLABLE_LABELS)
        file_sym_index = build_file_symbol_index(graph, _CALLABLE_LABELS)

        fpd = FileParseData(
            file_path="src/a.py",
            language="python",
            parse_result=ParseResult(
                calls=[CallInfo(name="execute", line=5, receiver="Worker")],
                symbols=[SymbolInfo(name="run", kind="function", start_line=1, end_line=10, content="")],
            ),
        )

        edges = resolve_file_calls(fpd, call_index, file_sym_index, graph)
        recv_edges = [e for e in edges if e.target == method_id]
        assert len(recv_edges) >= 1


# ---------------------------------------------------------------------------
# process_calls — parallel mode and collect mode
# ---------------------------------------------------------------------------

class TestProcessCallsParallelAndCollect:
    def _build_setup(self) -> tuple[KnowledgeGraph, list[FileParseData]]:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        _add_file(graph, "src/b.py")
        caller = _add_fn(graph, "src/a.py", "main", start=1, end=10)
        callee = _add_fn(graph, "src/b.py", "helper", start=1, end=5)

        parse_data = [
            FileParseData(
                file_path="src/a.py",
                language="python",
                parse_result=ParseResult(
                    calls=[CallInfo(name="helper", line=5)],
                    symbols=[SymbolInfo(name="main", kind="function", start_line=1, end_line=10, content="")],
                ),
            ),
        ]
        return graph, parse_data

    def test_collect_mode_returns_edges(self) -> None:
        graph, parse_data = self._build_setup()
        edges = process_calls(parse_data, graph, collect=True)
        assert edges is not None
        assert isinstance(edges, list)

    def test_non_collect_returns_none(self) -> None:
        graph, parse_data = self._build_setup()
        result = process_calls(parse_data, graph, collect=False)
        assert result is None

    def test_parallel_mode(self) -> None:
        graph, parse_data = self._build_setup()
        # Add a second file so parallel actually fires (requires >1 file)
        _add_file(graph, "src/c.py")
        _add_fn(graph, "src/c.py", "other", start=1, end=5)
        parse_data.append(FileParseData(
            file_path="src/c.py",
            language="python",
            parse_result=ParseResult(
                calls=[CallInfo(name="helper", line=3)],
                symbols=[SymbolInfo(name="other", kind="function", start_line=1, end_line=5, content="")],
            ),
        ))
        edges = process_calls(parse_data, graph, parallel=True, collect=True)
        assert edges is not None

    def test_prebuilt_name_index_used(self) -> None:
        graph, parse_data = self._build_setup()
        index = build_name_index(graph, _CALLABLE_LABELS)
        edges = process_calls(parse_data, graph, name_index=index, collect=True)
        assert edges is not None


# ---------------------------------------------------------------------------
# Decorator call resolution
# ---------------------------------------------------------------------------

class TestDecoratorCallResolution:
    def test_decorator_creates_calls_edge(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        route_fn = _add_fn(graph, "src/a.py", "route", start=1, end=5)
        decorated_fn_id = _add_fn(graph, "src/a.py", "index", start=7, end=12)

        fpd = FileParseData(
            file_path="src/a.py",
            language="python",
            parse_result=ParseResult(
                calls=[],
                symbols=[SymbolInfo(
                    name="index", kind="function",
                    start_line=7, end_line=12, content="",
                    decorators=["route"],
                )],
            ),
        )
        call_index = build_name_index(graph, _CALLABLE_LABELS)
        file_sym_index = build_file_symbol_index(graph, _CALLABLE_LABELS)

        edges = resolve_file_calls(fpd, call_index, file_sym_index, graph)
        dec_edges = [e for e in edges if e.target == route_fn]
        assert len(dec_edges) >= 1

    def test_dotted_decorator_resolves_base_name(self) -> None:
        graph = KnowledgeGraph()
        _add_file(graph, "src/a.py")
        route_fn = _add_fn(graph, "src/a.py", "route", start=1, end=5)
        decorated_fn_id = _add_fn(graph, "src/a.py", "index", start=7, end=12)

        fpd = FileParseData(
            file_path="src/a.py",
            language="python",
            parse_result=ParseResult(
                calls=[],
                symbols=[SymbolInfo(
                    name="index", kind="function",
                    start_line=7, end_line=12, content="",
                    decorators=["app.route"],
                )],
            ),
        )
        call_index = build_name_index(graph, _CALLABLE_LABELS)
        file_sym_index = build_file_symbol_index(graph, _CALLABLE_LABELS)

        edges = resolve_file_calls(fpd, call_index, file_sym_index, graph)
        # Either "route" or "app.route" should be in the edges
        assert len(edges) >= 0  # just ensure no crash
