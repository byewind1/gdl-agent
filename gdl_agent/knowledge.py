"""
Knowledge management for GDL Agent.

Loads reference documents from the knowledge/ directory and injects them
into LLM prompts. Supports both full-document injection (for models with
large context windows) and simple keyword-based relevance filtering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class KnowledgeBase:
    """
    Manages GDL reference documentation for RAG-style prompt injection.

    The knowledge base is a directory of Markdown files that contain:
    - GDL syntax reference
    - XML structure templates
    - Common error patterns and fixes

    These are loaded into the LLM's system prompt to compensate for the
    scarcity of GDL training data.
    """

    def __init__(self, knowledge_dir: str = "./knowledge"):
        self.knowledge_dir = Path(knowledge_dir)
        self._docs: dict[str, str] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all .md files from the knowledge directory."""
        self._docs.clear()

        if not self.knowledge_dir.exists():
            self._loaded = True
            return

        for md_file in sorted(self.knowledge_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                self._docs[md_file.stem] = content
            except Exception:
                continue

        self._loaded = True

    def get_all(self) -> str:
        """
        Get all knowledge documents concatenated.

        Suitable for models with large context windows (128k+).
        """
        if not self._loaded:
            self.load()

        if not self._docs:
            return ""

        parts = []
        for name, content in self._docs.items():
            parts.append(f"## {name}\n\n{content}")

        return "\n\n---\n\n".join(parts)

    def get_relevant(self, query: str, max_docs: int = 3) -> str:
        """
        Get knowledge documents relevant to a query.

        Uses simple keyword matching. For production use, consider
        replacing with embedding-based retrieval.

        Args:
            query: The user's instruction or error message.
            max_docs: Maximum number of documents to return.

        Returns:
            Concatenated relevant documents.
        """
        if not self._loaded:
            self.load()

        if not self._docs:
            return ""

        query_lower = query.lower()

        # Score each document by keyword overlap
        scored = []
        for name, content in self._docs.items():
            score = 0
            content_lower = content.lower()
            name_lower = name.lower()

            # Name match (high weight)
            for word in query_lower.split():
                if len(word) > 2:
                    if word in name_lower:
                        score += 10
                    if word in content_lower:
                        score += 1

            # Special keyword boosts
            error_keywords = ["error", "bug", "fix", "fail", "wrong", "错误", "报错", "失败"]
            if any(kw in query_lower for kw in error_keywords):
                if "error" in name_lower or "common" in name_lower:
                    score += 20

            syntax_keywords = ["prism", "revolve", "extrude", "tube", "命令", "语法", "syntax"]
            if any(kw in query_lower for kw in syntax_keywords):
                if "reference" in name_lower or "guide" in name_lower:
                    score += 20

            template_keywords = ["xml", "template", "structure", "结构", "模板"]
            if any(kw in query_lower for kw in template_keywords):
                if "template" in name_lower or "xml" in name_lower:
                    score += 20

            if score > 0:
                scored.append((score, name, content))

        # If no matches, return all docs (better safe than sorry)
        if not scored:
            return self.get_all()

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:max_docs]

        parts = []
        for _, name, content in top:
            parts.append(f"## {name}\n\n{content}")

        return "\n\n---\n\n".join(parts)

    @property
    def doc_count(self) -> int:
        if not self._loaded:
            self.load()
        return len(self._docs)

    @property
    def doc_names(self) -> list[str]:
        if not self._loaded:
            self.load()
        return list(self._docs.keys())
