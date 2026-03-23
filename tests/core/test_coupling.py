from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axon.core.graph.graph import KnowledgeGraph
from axon.core.graph.model import GraphNode, NodeLabel, RelType, generate_id
from axon.core.ingestion.coupling import (
    build_cochange_matrix,
    calculate_coupling,
    parse_git_log,
    process_coupling,
    resolve_coupling,
)


@pytest.fixture()
def graph() -> KnowledgeGraph:
    """Return a KnowledgeGraph pre-populated with File nodes.

    Layout:
    - File:src/auth.py
    - File:src/models.py
    - File:src/views.py
    - File:src/utils.py
    """
    g = KnowledgeGraph()

    for path in ("src/auth.py", "src/models.py", "src/views.py", "src/utils.py"):
        g.add_node(
            GraphNode(
                id=generate_id(NodeLabel.FILE, path),
                label=NodeLabel.FILE,
                name=path.split("/")[-1],
                file_path=path,
            )
        )

    return g

class TestBuildCochangeMatrix:
    def test_build_cochange_matrix(self) -> None:
        commits = [
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/views.py", "src/utils.py"],
        ]
        matrix, total = build_cochange_matrix(commits, min_cochanges=1)

        pair = ("src/auth.py", "src/models.py")
        assert pair in matrix
        assert matrix[pair] == 3

        pair_vu = ("src/utils.py", "src/views.py")
        assert pair_vu in matrix
        assert matrix[pair_vu] == 1

        assert total["src/auth.py"] == 3
        assert total["src/models.py"] == 3
        assert total["src/views.py"] == 1

    def test_build_cochange_matrix_min_threshold(self) -> None:
        commits = [
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/views.py", "src/utils.py"],
        ]
        matrix, _ = build_cochange_matrix(commits, min_cochanges=3)

        # auth+models has 3 co-changes, should be included.
        assert ("src/auth.py", "src/models.py") in matrix

        # views+utils has only 1, should be filtered.
        assert ("src/utils.py", "src/views.py") not in matrix

    def test_build_cochange_matrix_empty(self) -> None:
        matrix, total = build_cochange_matrix([], min_cochanges=1)
        assert matrix == {}
        assert total == {}

class TestCalculateCoupling:
    def test_calculate_coupling(self) -> None:
        total_changes = {"src/auth.py": 10, "src/models.py": 5}
        strength = calculate_coupling(
            "src/auth.py", "src/models.py", co_changes=5, total_changes=total_changes
        )
        # 5 / max(10, 5) = 5 / 10 = 0.5
        assert strength == pytest.approx(0.5)

    def test_calculate_coupling_equal_changes(self) -> None:
        total_changes = {"src/auth.py": 8, "src/models.py": 8}
        strength = calculate_coupling(
            "src/auth.py", "src/models.py", co_changes=6, total_changes=total_changes
        )
        # 6 / max(8, 8) = 6 / 8 = 0.75
        assert strength == pytest.approx(0.75)

    def test_calculate_coupling_zero_total_changes(self) -> None:
        total_changes = {"src/auth.py": 0, "src/models.py": 0}
        strength = calculate_coupling(
            "src/auth.py", "src/models.py", co_changes=0, total_changes=total_changes
        )
        assert strength == 0.0

class TestProcessCoupling:
    def test_process_coupling_creates_relationships(
        self, graph: KnowledgeGraph
    ) -> None:
        # auth.py and models.py change together 4 times out of 5 commits each.
        # views.py and utils.py change together only once.
        commits = [
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py"],
            ["src/models.py"],
            ["src/views.py", "src/utils.py"],
        ]

        count = process_coupling(
            graph,
            Path("/fake/repo"),
            min_strength=0.3,
            commits=commits,
            min_cochanges=1,
        )

        # auth+models: coupling = 4 / max(5, 5) = 0.8 >= 0.3 -> created
        # views+utils: coupling = 1 / max(1, 1) = 1.0 >= 0.3 -> created
        assert count == 2

        coupled_rels = graph.get_relationships_by_type(RelType.COUPLED_WITH)
        assert len(coupled_rels) == 2

        # Verify properties on the auth+models relationship.
        auth_id = generate_id(NodeLabel.FILE, "src/auth.py")
        models_id = generate_id(NodeLabel.FILE, "src/models.py")

        auth_models_rel = next(
            (
                r
                for r in coupled_rels
                if r.source == auth_id and r.target == models_id
            ),
            None,
        )
        assert auth_models_rel is not None
        assert auth_models_rel.properties["strength"] == pytest.approx(0.8)
        assert auth_models_rel.properties["co_changes"] == 4

    def test_process_coupling_no_git(self, graph: KnowledgeGraph) -> None:
        count = process_coupling(
            graph,
            Path("/nonexistent/repo"),
            min_strength=0.3,
            commits=[],
        )
        assert count == 0

        coupled_rels = graph.get_relationships_by_type(RelType.COUPLED_WITH)
        assert len(coupled_rels) == 0

    def test_process_coupling_filters_weak_pairs(
        self, graph: KnowledgeGraph
    ) -> None:
        # auth changes 10 times, models 10 times, but they co-change only twice.
        # coupling = 2/10 = 0.2 which is below min_strength=0.3
        commits = [
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py"],
            ["src/auth.py"],
            ["src/auth.py"],
            ["src/auth.py"],
            ["src/auth.py"],
            ["src/auth.py"],
            ["src/models.py"],
            ["src/models.py"],
            ["src/models.py"],
            ["src/models.py"],
            ["src/models.py"],
            ["src/models.py"],
        ]

        count = process_coupling(
            graph,
            Path("/fake/repo"),
            min_strength=0.3,
            commits=commits,
        )
        assert count == 0

    def test_process_coupling_relationship_id_format(
        self, graph: KnowledgeGraph
    ) -> None:
        commits = [
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
        ]

        process_coupling(
            graph,
            Path("/fake/repo"),
            min_strength=0.3,
            commits=commits,
        )

        coupled_rels = graph.get_relationships_by_type(RelType.COUPLED_WITH)
        assert len(coupled_rels) >= 1

        for rel in coupled_rels:
            assert rel.id.startswith("coupled:")
            assert "->" in rel.id


# ---------------------------------------------------------------------------
# parse_git_log — error handling paths
# ---------------------------------------------------------------------------

class TestParseGitLog:
    def test_returns_empty_on_nonzero_returncode(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("axon.core.ingestion.coupling.subprocess.run", return_value=mock_result):
            commits = parse_git_log(tmp_path)
        assert commits == []

    def test_returns_empty_on_timeout(self, tmp_path: Path) -> None:
        import subprocess
        with patch("axon.core.ingestion.coupling.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("git", 30)):
            commits = parse_git_log(tmp_path)
        assert commits == []

    def test_returns_empty_on_file_not_found(self, tmp_path: Path) -> None:
        with patch("axon.core.ingestion.coupling.subprocess.run",
                   side_effect=FileNotFoundError("git not found")):
            commits = parse_git_log(tmp_path)
        assert commits == []

    def test_parses_commit_output(self, tmp_path: Path) -> None:
        git_output = "COMMIT:abc123\nsrc/foo.py\nsrc/bar.py\n\nCOMMIT:def456\nsrc/foo.py\n"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = git_output
        with patch("axon.core.ingestion.coupling.subprocess.run", return_value=mock_result):
            commits = parse_git_log(tmp_path)
        assert len(commits) == 2
        assert "src/foo.py" in commits[0]
        assert "src/bar.py" in commits[0]
        assert "src/foo.py" in commits[1]


# ---------------------------------------------------------------------------
# build_cochange_matrix — large commit skip
# ---------------------------------------------------------------------------

class TestBuildCochangeMatrixLargeCommit:
    def test_large_commit_skipped(self) -> None:
        # Create a commit with 51 files (> max_files_per_commit=50).
        large_commit = [f"src/file{i}.py" for i in range(51)]
        small_commit = ["src/a.py", "src/b.py", "src/a.py", "src/b.py", "src/a.py"]

        matrix, total = build_cochange_matrix(
            [large_commit, small_commit, small_commit, small_commit],
            min_cochanges=1,
        )

        # The large commit pair should NOT be in the matrix.
        for pair in matrix:
            for f in pair:
                assert f.startswith("src/a") or f.startswith("src/b"), (
                    f"Large commit files should not appear in matrix: {f}"
                )


# ---------------------------------------------------------------------------
# resolve_coupling — file-not-in-graph and below-strength-threshold paths
# ---------------------------------------------------------------------------

class TestResolveCouplingEdgeCases:
    def test_file_not_in_graph_skipped(self) -> None:
        """Pairs where one file is not in the graph produce no edges."""
        graph = KnowledgeGraph()
        # Only add auth.py to the graph — models.py is absent.
        graph.add_node(GraphNode(
            id=generate_id(NodeLabel.FILE, "src/auth.py"),
            label=NodeLabel.FILE,
            name="auth.py",
            file_path="src/auth.py",
        ))

        commits = [
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
            ["src/auth.py", "src/models.py"],
        ]
        edges = resolve_coupling(graph, Path("/fake"), min_strength=0.3, commits=commits, min_cochanges=1)
        assert edges == []

    def test_low_strength_pair_skipped(self) -> None:
        """Pairs below min_strength but above min_cochanges produce no edges."""
        graph = KnowledgeGraph()
        for path in ("src/a.py", "src/b.py"):
            graph.add_node(GraphNode(
                id=generate_id(NodeLabel.FILE, path),
                label=NodeLabel.FILE,
                name=path.split("/")[-1],
                file_path=path,
            ))

        # a+b co-change 3 times; a changes 20 times total.
        # coupling = min(3/20, 3/3) = 0.15 < min_strength=0.3
        commits = [["src/a.py", "src/b.py"]] * 3 + [["src/a.py"]] * 17
        edges = resolve_coupling(graph, Path("/fake"), min_strength=0.3, commits=commits, min_cochanges=1)
        assert edges == []
