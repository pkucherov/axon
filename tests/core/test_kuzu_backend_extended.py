"""Extended tests for KuzuBackend covering previously uncovered code paths."""
from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import patch

import pytest

from axon.core.graph.graph import KnowledgeGraph
from axon.core.graph.model import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelType,
    generate_id,
)
from axon.core.storage.base import NodeEmbedding
from axon.core.storage.kuzu_backend import KuzuBackend, _safe_vec_literal, escape_cypher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def backend(tmp_path: Path) -> KuzuBackend:
    db_path = tmp_path / "test_db"
    b = KuzuBackend()
    b.initialize(db_path)
    yield b
    b.close()


def _fn(name: str, file_path: str = "src/a.py", **kwargs) -> GraphNode:
    return GraphNode(
        id=generate_id(NodeLabel.FUNCTION, file_path, name),
        label=NodeLabel.FUNCTION,
        name=name,
        file_path=file_path,
        **kwargs,
    )


def _cls(name: str, file_path: str = "src/a.py") -> GraphNode:
    return GraphNode(
        id=generate_id(NodeLabel.CLASS, file_path, name),
        label=NodeLabel.CLASS,
        name=name,
        file_path=file_path,
    )


def _rel(src: str, tgt: str, rel_type: RelType = RelType.CALLS) -> GraphRelationship:
    return GraphRelationship(
        id=f"{rel_type.value}:{src}->{tgt}",
        type=rel_type,
        source=src,
        target=tgt,
    )


# ---------------------------------------------------------------------------
# _safe_vec_literal
# ---------------------------------------------------------------------------

class TestSafeVecLiteral:
    def test_finite_values(self) -> None:
        result = _safe_vec_literal([1.0, 2.5, -0.3])
        assert result.startswith("[")
        assert result.endswith("]")

    def test_raises_on_inf(self) -> None:
        with pytest.raises(ValueError, match="Non-finite"):
            _safe_vec_literal([1.0, math.inf])

    def test_raises_on_nan(self) -> None:
        with pytest.raises(ValueError, match="Non-finite"):
            _safe_vec_literal([math.nan])


# ---------------------------------------------------------------------------
# escape_cypher
# ---------------------------------------------------------------------------

class TestEscapeCypher:
    def test_removes_null_bytes(self) -> None:
        assert "\x00" not in escape_cypher("hel\x00lo")

    def test_removes_comment_sequences(self) -> None:
        result = escape_cypher("/* comment */ x // inline")
        assert "/*" not in result
        assert "*/" not in result
        assert "//" not in result

    def test_removes_semicolons(self) -> None:
        assert ";" not in escape_cypher("DROP TABLE; SELECT 1")

    def test_escapes_backslash(self) -> None:
        result = escape_cypher("path\\to\\file")
        assert "\\\\" in result

    def test_escapes_single_quote(self) -> None:
        result = escape_cypher("it's")
        assert "\\'" in result


# ---------------------------------------------------------------------------
# _require_conn
# ---------------------------------------------------------------------------

class TestRequireConn:
    def test_raises_before_initialize(self) -> None:
        b = KuzuBackend()
        with pytest.raises(RuntimeError, match="initialize"):
            b._require_conn()


# ---------------------------------------------------------------------------
# get_file_index
# ---------------------------------------------------------------------------

class TestGetFileIndex:
    def test_empty_initially(self, backend: KuzuBackend) -> None:
        result = backend.get_file_index()
        assert result == {}

    def test_returns_file_paths_after_insert(self, backend: KuzuBackend) -> None:
        node = GraphNode(
            id=generate_id(NodeLabel.FILE, "src/main.py", ""),
            label=NodeLabel.FILE,
            name="main.py",
            file_path="src/main.py",
        )
        backend.add_nodes([node])
        result = backend.get_file_index()
        assert "src/main.py" in result
        assert result["src/main.py"] == node.id


# ---------------------------------------------------------------------------
# get_symbol_name_index
# ---------------------------------------------------------------------------

class TestGetSymbolNameIndex:
    def test_empty_initially(self, backend: KuzuBackend) -> None:
        result = backend.get_symbol_name_index()
        assert result == {}

    def test_indexes_functions_and_classes(self, backend: KuzuBackend) -> None:
        fn = _fn("my_func")
        cls = _cls("MyClass")
        backend.add_nodes([fn, cls])

        result = backend.get_symbol_name_index()
        assert "my_func" in result
        assert fn.id in result["my_func"]
        assert "MyClass" in result
        assert cls.id in result["MyClass"]

    def test_multiple_symbols_with_same_name(self, backend: KuzuBackend) -> None:
        fn1 = _fn("process", file_path="src/a.py")
        fn2 = _fn("process", file_path="src/b.py")
        backend.add_nodes([fn1, fn2])

        result = backend.get_symbol_name_index()
        assert len(result["process"]) == 2


# ---------------------------------------------------------------------------
# get_inbound_cross_file_edges
# ---------------------------------------------------------------------------

class TestGetInboundCrossFileEdges:
    def test_returns_empty_with_no_edges(self, backend: KuzuBackend) -> None:
        edges = backend.get_inbound_cross_file_edges("src/target.py")
        assert edges == []

    def test_returns_cross_file_calls(self, backend: KuzuBackend) -> None:
        caller = _fn("caller", "src/a.py")
        callee = _fn("callee", "src/b.py")
        backend.add_nodes([caller, callee])
        backend.add_relationships([_rel(caller.id, callee.id, RelType.CALLS)])

        edges = backend.get_inbound_cross_file_edges("src/b.py")
        assert len(edges) == 1
        assert edges[0].source == caller.id
        assert edges[0].target == callee.id
        assert edges[0].type == RelType.CALLS

    def test_excludes_same_file_edges(self, backend: KuzuBackend) -> None:
        fn1 = _fn("fn1", "src/same.py")
        fn2 = _fn("fn2", "src/same.py")
        backend.add_nodes([fn1, fn2])
        backend.add_relationships([_rel(fn1.id, fn2.id)])

        edges = backend.get_inbound_cross_file_edges("src/same.py")
        assert edges == []

    def test_excludes_source_files_filter(self, backend: KuzuBackend) -> None:
        caller = _fn("caller", "src/a.py")
        callee = _fn("callee", "src/b.py")
        backend.add_nodes([caller, callee])
        backend.add_relationships([_rel(caller.id, callee.id)])

        edges = backend.get_inbound_cross_file_edges(
            "src/b.py", exclude_source_files={"src/a.py"}
        )
        assert edges == []


# ---------------------------------------------------------------------------
# exact_name_search
# ---------------------------------------------------------------------------

class TestExactNameSearch:
    def test_finds_function_by_name(self, backend: KuzuBackend) -> None:
        fn = _fn("target_func", content="def target_func(): pass")
        backend.add_nodes([fn])
        backend.rebuild_fts_indexes()

        results = backend.exact_name_search("target_func")
        assert len(results) >= 1
        names = [r.node_name for r in results]
        assert "target_func" in names

    def test_returns_empty_for_no_match(self, backend: KuzuBackend) -> None:
        results = backend.exact_name_search("nonexistent_xyz_abc")
        assert results == []

    def test_test_file_gets_lower_score(self, backend: KuzuBackend) -> None:
        src_fn = _fn("shared", "src/app.py")
        # Path must contain "/tests/" (with leading slash) to trigger the penalty
        test_fn = GraphNode(
            id=generate_id(NodeLabel.FUNCTION, "src/tests/test_app.py", "shared"),
            label=NodeLabel.FUNCTION,
            name="shared",
            file_path="src/tests/test_app.py",
        )
        backend.add_nodes([src_fn, test_fn])

        results = backend.exact_name_search("shared")
        assert len(results) == 2
        src_result = next(r for r in results if "/tests/" not in r.file_path)
        test_result = next(r for r in results if "/tests/" in r.file_path)
        assert src_result.score > test_result.score


# ---------------------------------------------------------------------------
# fuzzy_search
# ---------------------------------------------------------------------------

class TestFuzzySearch:
    def test_finds_close_match(self, backend: KuzuBackend) -> None:
        fn = _fn("validate")
        backend.add_nodes([fn])

        results = backend.fuzzy_search("validete", limit=5, max_distance=2)
        names = [r.node_name for r in results]
        assert "validate" in names

    def test_returns_empty_for_distant_query(self, backend: KuzuBackend) -> None:
        fn = _fn("validate")
        backend.add_nodes([fn])

        results = backend.fuzzy_search("xxxxxx", limit=5, max_distance=1)
        assert results == []

    def test_exact_match_gets_best_score(self, backend: KuzuBackend) -> None:
        fn = _fn("process")
        backend.add_nodes([fn])

        results = backend.fuzzy_search("process", limit=5, max_distance=2)
        assert len(results) >= 1
        assert results[0].score == 1.0


# ---------------------------------------------------------------------------
# vector_search
# ---------------------------------------------------------------------------

class TestVectorSearch:
    def test_returns_empty_with_no_embeddings(self, backend: KuzuBackend) -> None:
        results = backend.vector_search([0.1, 0.2, 0.3], limit=5)
        assert results == []

    def test_finds_stored_embedding(self, backend: KuzuBackend) -> None:
        fn = _fn("embed_func")
        backend.add_nodes([fn])

        emb = NodeEmbedding(node_id=fn.id, embedding=[1.0, 0.0, 0.0])
        backend.store_embeddings([emb])

        results = backend.vector_search([1.0, 0.0, 0.0], limit=5)
        assert len(results) >= 1
        ids = [r.node_id for r in results]
        assert fn.id in ids

    def test_raises_on_non_finite_vector(self, backend: KuzuBackend) -> None:
        with pytest.raises(ValueError):
            backend.vector_search([1.0, math.inf], limit=5)


# ---------------------------------------------------------------------------
# get_type_refs
# ---------------------------------------------------------------------------

class TestGetTypeRefs:
    def test_returns_empty_for_unknown_label(self, backend: KuzuBackend) -> None:
        results = backend.get_type_refs("unknown:foo:bar")
        assert results == []

    def test_finds_uses_type_relationship(self, backend: KuzuBackend) -> None:
        fn = _fn("validate")
        cls = _cls("UserType")
        backend.add_nodes([fn, cls])
        backend.add_relationships([
            GraphRelationship(
                id=f"uses_type:{fn.id}->{cls.id}",
                type=RelType.USES_TYPE,
                source=fn.id,
                target=cls.id,
            )
        ])

        refs = backend.get_type_refs(fn.id)
        assert len(refs) == 1
        assert refs[0].name == "UserType"


# ---------------------------------------------------------------------------
# get_callers_with_confidence / get_callees_with_confidence
# ---------------------------------------------------------------------------

class TestCallsWithConfidence:
    def _setup(self, backend: KuzuBackend) -> tuple[str, str]:
        caller = _fn("caller")
        callee = _fn("callee")
        backend.add_nodes([caller, callee])
        rel = GraphRelationship(
            id=f"calls:{caller.id}->{callee.id}",
            type=RelType.CALLS,
            source=caller.id,
            target=callee.id,
            properties={"confidence": 0.85},
        )
        backend.add_relationships([rel])
        return caller.id, callee.id

    def test_get_callers_with_confidence_unknown_label(self, backend: KuzuBackend) -> None:
        result = backend.get_callers_with_confidence("unknown:x:y")
        assert result == []

    def test_get_callees_with_confidence_unknown_label(self, backend: KuzuBackend) -> None:
        result = backend.get_callees_with_confidence("unknown:x:y")
        assert result == []

    def test_get_callers_with_confidence_returns_pair(self, backend: KuzuBackend) -> None:
        caller_id, callee_id = self._setup(backend)
        pairs = backend.get_callers_with_confidence(callee_id)
        assert len(pairs) == 1
        node, conf = pairs[0]
        assert node.name == "caller"
        assert isinstance(conf, float)

    def test_get_callees_with_confidence_returns_pair(self, backend: KuzuBackend) -> None:
        caller_id, callee_id = self._setup(backend)
        pairs = backend.get_callees_with_confidence(caller_id)
        assert len(pairs) == 1
        node, conf = pairs[0]
        assert node.name == "callee"
        assert isinstance(conf, float)


# ---------------------------------------------------------------------------
# traverse_with_depth
# ---------------------------------------------------------------------------

class TestTraverseWithDepth:
    def test_returns_empty_for_unknown_label(self, backend: KuzuBackend) -> None:
        result = backend.traverse_with_depth("unknown:x:y", depth=2)
        assert result == []

    def test_hop_depth_is_correct(self, backend: KuzuBackend) -> None:
        a = _fn("a", "src/a.py")
        b = _fn("b", "src/b.py")
        c = _fn("c", "src/c.py")
        backend.add_nodes([a, b, c])
        backend.add_relationships([
            _rel(a.id, b.id),
            _rel(b.id, c.id),
        ])

        pairs = backend.traverse_with_depth(a.id, depth=2, direction="callees")
        by_name = {node.name: depth for node, depth in pairs}
        assert by_name["b"] == 1
        assert by_name["c"] == 2

    def test_depth_cap_respected(self, backend: KuzuBackend) -> None:
        a = _fn("a", "src/a.py")
        b = _fn("b", "src/b.py")
        c = _fn("c", "src/c.py")
        backend.add_nodes([a, b, c])
        backend.add_relationships([
            _rel(a.id, b.id),
            _rel(b.id, c.id),
        ])

        pairs = backend.traverse_with_depth(a.id, depth=1, direction="callees")
        names = {node.name for node, _ in pairs}
        assert "b" in names
        assert "c" not in names


# ---------------------------------------------------------------------------
# get_process_memberships
# ---------------------------------------------------------------------------

class TestGetProcessMemberships:
    def test_returns_empty_for_empty_input(self, backend: KuzuBackend) -> None:
        result = backend.get_process_memberships([])
        assert result == {}

    def test_returns_mapping_when_in_process(self, backend: KuzuBackend) -> None:
        fn = _fn("entry")
        proc = GraphNode(
            id=generate_id(NodeLabel.PROCESS, "", "my_process"),
            label=NodeLabel.PROCESS,
            name="my_process",
            file_path="",
        )
        backend.add_nodes([fn, proc])
        backend.add_relationships([
            GraphRelationship(
                id=f"step_in_process:{fn.id}->{proc.id}",
                type=RelType.STEP_IN_PROCESS,
                source=fn.id,
                target=proc.id,
            )
        ])

        result = backend.get_process_memberships([fn.id])
        assert fn.id in result
        assert result[fn.id] == "my_process"

    def test_returns_empty_for_no_match(self, backend: KuzuBackend) -> None:
        fn = _fn("standalone")
        backend.add_nodes([fn])
        result = backend.get_process_memberships([fn.id])
        assert result == {}


# ---------------------------------------------------------------------------
# load_graph — relationship property round-trip
# ---------------------------------------------------------------------------

class TestLoadGraphRelationshipProperties:
    def test_relationship_with_all_properties(self, backend: KuzuBackend) -> None:
        a = _fn("a")
        b = _fn("b")
        backend.add_nodes([a, b])

        rel = GraphRelationship(
            id=f"calls:{a.id}->{b.id}",
            type=RelType.CALLS,
            source=a.id,
            target=b.id,
            properties={
                "confidence": 0.9,
                "role": "direct",
                "step_number": 2,
                "strength": 0.7,
                "co_changes": 5,
                "symbols": "foo,bar",
            },
        )
        backend.add_relationships([rel])

        graph = backend.load_graph()
        loaded_rels = list(graph.iter_relationships())
        assert len(loaded_rels) == 1
        r = loaded_rels[0]
        props = r.properties or {}
        assert abs(props.get("confidence", 0) - 0.9) < 0.001
        assert props.get("role") == "direct"
        assert props.get("step_number") == 2
        assert abs(props.get("strength", 0) - 0.7) < 0.001
        assert props.get("co_changes") == 5
        assert props.get("symbols") == "foo,bar"


# ---------------------------------------------------------------------------
# _row_to_node — edge cases
# ---------------------------------------------------------------------------

class TestRowToNodeEdgeCases:
    def test_unknown_label_prefix_returns_none(self, backend: KuzuBackend) -> None:
        node = KuzuBackend._row_to_node(
            ["badlabel:src/a.py:foo", "foo", "src/a.py", 0, 0,
             "", "", "", "", False, False, False, None, None]
        )
        assert node is None

    def test_index_error_returns_none(self) -> None:
        node = KuzuBackend._row_to_node([])
        assert node is None

    def test_parses_cohesion_property(self, backend: KuzuBackend) -> None:
        node = GraphNode(
            id=generate_id(NodeLabel.FUNCTION, "src/a.py", "cohesive"),
            label=NodeLabel.FUNCTION,
            name="cohesive",
            file_path="src/a.py",
            properties={"cohesion": 0.75},
        )
        backend.add_nodes([node])

        loaded = backend.get_node(node.id)
        assert loaded is not None
        props = loaded.properties or {}
        assert abs(props.get("cohesion", 0) - 0.75) < 0.01

    def test_parses_extra_json_properties(self, backend: KuzuBackend) -> None:
        node = GraphNode(
            id=generate_id(NodeLabel.FUNCTION, "src/a.py", "extra_props"),
            label=NodeLabel.FUNCTION,
            name="extra_props",
            file_path="src/a.py",
            properties={"my_custom_key": "hello"},
        )
        backend.add_nodes([node])

        loaded = backend.get_node(node.id)
        assert loaded is not None
        props = loaded.properties or {}
        assert props.get("my_custom_key") == "hello"


# ---------------------------------------------------------------------------
# _insert_relationship with unresolvable table
# ---------------------------------------------------------------------------

class TestInsertRelationshipEdgeCases:
    def test_skips_relationship_with_unknown_source_table(
        self, backend: KuzuBackend
    ) -> None:
        rel = GraphRelationship(
            id="calls:unknown:a->function:src/a.py:b",
            type=RelType.CALLS,
            source="unknown:a",
            target="function:src/a.py:b",
        )
        backend.add_relationships([rel])
        graph = backend.load_graph()
        assert graph.relationship_count == 0

    def test_skips_relationship_with_unknown_target_table(
        self, backend: KuzuBackend
    ) -> None:
        fn = _fn("source_fn")
        backend.add_nodes([fn])
        rel = GraphRelationship(
            id=f"calls:{fn.id}->unknown:b",
            type=RelType.CALLS,
            source=fn.id,
            target="unknown:b",
        )
        backend.add_relationships([rel])
        graph = backend.load_graph()
        assert graph.relationship_count == 0


# ---------------------------------------------------------------------------
# store_embeddings — empty input
# ---------------------------------------------------------------------------

class TestStoreEmbeddingsEdgeCases:
    def test_empty_list_is_noop(self, backend: KuzuBackend) -> None:
        backend.store_embeddings([])
        rows = backend.execute_raw("MATCH (e:Embedding) RETURN count(e)")
        assert rows[0][0] == 0


# ---------------------------------------------------------------------------
# delete_synthetic_nodes — empty DB is safe
# ---------------------------------------------------------------------------

class TestDeleteSyntheticNodesEmpty:
    def test_safe_on_empty_db(self, backend: KuzuBackend) -> None:
        backend.delete_synthetic_nodes()
        graph = backend.load_graph()
        assert graph.node_count == 0


# ---------------------------------------------------------------------------
# update_dead_flags — empty inputs
# ---------------------------------------------------------------------------

class TestUpdateDeadFlagsEdgeCases:
    def test_empty_sets_noop(self, backend: KuzuBackend) -> None:
        fn = _fn("alive")
        backend.add_nodes([fn])
        backend.update_dead_flags(dead_ids=set(), alive_ids=set())
        loaded = backend.get_node(fn.id)
        assert loaded is not None
        assert loaded.is_dead is False


# ---------------------------------------------------------------------------
# remove_relationships_by_type — empty DB
# ---------------------------------------------------------------------------

class TestRemoveRelationshipsByTypeEdgeCases:
    def test_safe_on_empty_db(self, backend: KuzuBackend) -> None:
        backend.remove_relationships_by_type(RelType.CALLS)
        graph = backend.load_graph()
        assert graph.relationship_count == 0


# ---------------------------------------------------------------------------
# get_indexed_files — with multiple files
# ---------------------------------------------------------------------------

class TestGetIndexedFilesMultiple:
    def test_returns_all_files(self, backend: KuzuBackend) -> None:
        for name in ("a.py", "b.py", "c.py"):
            node = GraphNode(
                id=generate_id(NodeLabel.FILE, f"src/{name}", ""),
                label=NodeLabel.FILE,
                name=name,
                file_path=f"src/{name}",
                content=f"# {name}",
            )
            backend.add_nodes([node])

        result = backend.get_indexed_files()
        assert "src/a.py" in result
        assert "src/b.py" in result
        assert "src/c.py" in result
