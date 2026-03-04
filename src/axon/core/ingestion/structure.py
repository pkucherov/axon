"""Phase 2: Structure processing for Axon.

Takes a list of file entries (path, content, language) and populates the
knowledge graph with File and Folder nodes connected by CONTAINS relationships.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from axon.core.graph.graph import KnowledgeGraph
from axon.core.graph.model import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelType,
    generate_id,
)

if TYPE_CHECKING:
    from axon.core.ingestion.walker import FileEntry

def process_structure(files: list[FileEntry], graph: KnowledgeGraph) -> None:
    """Build File/Folder nodes and CONTAINS relationships from a list of files.

    For every file entry a :pyclass:`NodeLabel.FILE` node is created.  Every
    unique directory that appears in any file path produces a
    :pyclass:`NodeLabel.FOLDER` node.  Parent-child folder relationships and
    folder-to-file relationships are expressed as :pyclass:`RelType.CONTAINS`
    edges.

    Runs in two passes:
      1. Collect all unique folder paths from file entries.
      2. Create all nodes (folders + files) and edges (CONTAINS) in one loop each.

    Args:
        files: File entries to process.  Each entry carries the relative path,
            raw content, and detected language.
        graph: The knowledge graph to populate.  Nodes and relationships are
            **added** (existing content is not removed).
    """
    # Pass 1: collect unique folder paths.
    folder_paths: set[str] = set()
    for file_info in files:
        pure = PurePosixPath(file_info.path)
        for parent in pure.parents:
            parent_str = str(parent)
            if parent_str == ".":
                continue
            folder_paths.add(parent_str)

    # Pass 2: create all nodes and edges.
    for dir_path in folder_paths:
        folder_id = generate_id(NodeLabel.FOLDER, dir_path)
        if graph.get_node(folder_id) is None:
            graph.add_node(
                GraphNode(
                    id=folder_id,
                    label=NodeLabel.FOLDER,
                    name=PurePosixPath(dir_path).name,
                    file_path=dir_path,
                )
            )
        # Folder → parent folder CONTAINS edge.
        dir_pure = PurePosixPath(dir_path)
        parent_str = str(dir_pure.parent)
        if parent_str != ".":
            parent_id = generate_id(NodeLabel.FOLDER, parent_str)
            rel_id = f"contains:{parent_id}->{folder_id}"
            graph.add_relationship(
                GraphRelationship(
                    id=rel_id,
                    type=RelType.CONTAINS,
                    source=parent_id,
                    target=folder_id,
                )
            )

    for file_info in files:
        file_id = generate_id(NodeLabel.FILE, file_info.path)
        graph.add_node(
            GraphNode(
                id=file_id,
                label=NodeLabel.FILE,
                name=PurePosixPath(file_info.path).name,
                file_path=file_info.path,
                content=file_info.content,
                language=file_info.language,
            )
        )
        # Folder → file CONTAINS edge.
        parent_str = str(PurePosixPath(file_info.path).parent)
        if parent_str != ".":
            parent_id = generate_id(NodeLabel.FOLDER, parent_str)
            rel_id = f"contains:{parent_id}->{file_id}"
            graph.add_relationship(
                GraphRelationship(
                    id=rel_id,
                    type=RelType.CONTAINS,
                    source=parent_id,
                    target=file_id,
                )
            )
