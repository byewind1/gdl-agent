"""
GDL Agent Core Loop — v0.3

Three-phase state machine:
  Phase 1 (Analyze):  Pre-flight check → context surgery → dependency resolution
  Phase 2 (Generate): LLM code generation → self-review → validation
  Phase 3 (Compile):  Sandbox write → compile → promote on success

Key v0.3 changes:
  - Sandbox compilation: source files are NEVER modified by failed attempts
  - Context surgery: LLM sees only relevant XML sections, saving tokens
  - Pre-flight analysis: detect blockers before burning LLM tokens
  - Self-review: LLM checks its own output for logical errors before compile
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol

from gdl_agent.config import GDLAgentConfig
from gdl_agent.context import slice_context
from gdl_agent.dependencies import DependencyResolver
from gdl_agent.knowledge import KnowledgeBase
from gdl_agent.llm import LLMResponse, Message
from gdl_agent.preflight import PreflightAnalyzer, AnalysisResult
from gdl_agent.sandbox import Sandbox, SandboxPaths
from gdl_agent.snippets import SnippetLibrary
from gdl_agent.xml_utils import (
    compute_diff,
    contents_identical,
    inject_debug_anchors,
    read_xml_file,
    validate_gdl_structure,
    validate_xml,
    write_xml_file,
)


# ── Protocols ──────────────────────────────────────────────────────────

class LLMProtocol(Protocol):
    def generate(self, messages: list[Message], **kwargs) -> LLMResponse: ...

class CompilerProtocol(Protocol):
    def is_available(self) -> bool: ...
    def compile(self, source: str, output: str) -> Any: ...


# ── Result Types ───────────────────────────────────────────────────────

class Status(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    EXHAUSTED = "exhausted"
    COMPILER_UNAVAILABLE = "compiler_unavailable"
    BLOCKED = "blocked"  # v0.3: pre-flight analysis found hard blockers


@dataclass
class AttemptRecord:
    attempt: int
    stage: str
    success: bool
    error: str = ""
    diff: str = ""
    duration_ms: int = 0


@dataclass
class AgentResult:
    status: Status
    attempts: int = 0
    output_path: str = ""
    error_summary: str = ""
    history: list[AttemptRecord] = field(default_factory=list)
    total_tokens: int = 0
    total_duration_ms: int = 0
    analysis: Optional[AnalysisResult] = None  # v0.3: preflight analysis

    @property
    def success(self) -> bool:
        return self.status == Status.SUCCESS


# ── Agent Core ─────────────────────────────────────────────────────────

class GDLAgent:
    """
    Three-phase GDL development agent.

    Phase 1 — ANALYZE:
      Pre-flight checks, context surgery, dependency resolution.
      Aborts early if hard blockers are found.

    Phase 2 — GENERATE:
      LLM generates code with focused context.
      Optional self-review catches logical errors before compile.

    Phase 3 — COMPILE:
      Sandbox compilation protects source files.
      Only promotes to source on success.
    """

    def __init__(
        self,
        config: GDLAgentConfig,
        llm: LLMProtocol,
        compiler: CompilerProtocol,
        knowledge: Optional[KnowledgeBase] = None,
        snippets: Optional[SnippetLibrary] = None,
        resolver: Optional[DependencyResolver] = None,
        sandbox: Optional[Sandbox] = None,
        on_event: Optional[callable] = None,
        debug_mode: bool = False,
        self_review: bool = True,
    ):
        self.config = config
        self.llm = llm
        self.compiler = compiler
        self.knowledge = knowledge or KnowledgeBase(config.knowledge_dir)
        self.snippets = snippets or SnippetLibrary()
        self.resolver = resolver or DependencyResolver(config.src_dir, config.templates_dir)
        self.sandbox = sandbox or Sandbox(config.src_dir, "./temp", config.output_dir)
        self.on_event = on_event or (lambda *a, **kw: None)
        self.debug_mode = debug_mode
        self.self_review = self_review
        self._analyzer = PreflightAnalyzer(self.resolver)

        # Load prompts
        self._system_prompt = self._load_prompt("system.md")
        self._error_prompt = self._load_prompt("error_analysis.md")
        self._review_prompt = self._load_prompt("self_review.md")

    def _load_prompt(self, filename: str) -> str:
        for base in [Path("prompts"), Path(__file__).parent / "prompts"]:
            path = base / filename
            if path.exists():
                return path.read_text(encoding="utf-8")
        return ""

    # ── Main Entry Point ──────────────────────────────────────────────

    def run(
        self,
        instruction: str,
        source_path: str,
        output_path: str,
    ) -> AgentResult:
        start_time = time.monotonic()
        max_iter = self.config.agent.max_iterations

        self.on_event("start", instruction=instruction, source=source_path,
                      max_iterations=max_iter)

        # ══════════════════════════════════════════════════════════
        # PHASE 1: ANALYZE
        # ══════════════════════════════════════════════════════════

        if not self.compiler.is_available():
            self.on_event("compiler_unavailable")
            return AgentResult(
                status=Status.COMPILER_UNAVAILABLE,
                error_summary="LP_XMLConverter not available.",
            )

        # Read source (golden copy)
        xml_content = ""
        source_p = Path(source_path)
        if source_p.exists():
            try:
                xml_content = read_xml_file(source_path)
                self.on_event("file_read", path=source_path, size=len(xml_content))
            except Exception as e:
                self.on_event("file_read_error", error=str(e))

        # Pre-flight analysis
        analysis = self._analyzer.analyze(instruction, xml_content)
        self.on_event("analysis_complete", summary=analysis.summary,
                      complexity=analysis.complexity)

        if not analysis.feasible:
            return AgentResult(
                status=Status.BLOCKED,
                error_summary="Pre-flight blocked: " + "; ".join(analysis.blockers),
                analysis=analysis,
            )

        # Context surgery: get focused XML for LLM
        if analysis.context_slice and not analysis.context_slice.is_full:
            focused_xml = analysis.context_slice.to_xml_string()
            self.on_event("context_sliced",
                          original=analysis.context_slice.total_chars,
                          sliced=analysis.context_slice.sliced_chars,
                          savings=analysis.context_slice.savings_pct)
        else:
            focused_xml = xml_content

        # Build knowledge + snippets + dependency context
        knowledge_text = self.knowledge.get_relevant(instruction)
        matched_snippets = self.snippets.match(instruction, xml_content)
        snippet_text = self.snippets.format_for_prompt(matched_snippets)
        if matched_snippets:
            self.on_event("snippets_matched", count=len(matched_snippets),
                          names=[s.name for s in matched_snippets])

        dependency_text = ""
        if xml_content:
            deps = self.resolver.resolve(xml_content)
            dependency_text = self.resolver.format_all_for_prompt(deps)
            if deps:
                self.on_event("deps_resolved", count=len(deps),
                              names=[d.name for d in deps])

        system_prompt = self._system_prompt.replace("{knowledge}", knowledge_text)
        system_prompt += snippet_text + dependency_text

        # Warn about unresolved macros
        if analysis.unresolved_macros:
            system_prompt += (
                "\n\n## ⚠️ Unresolved Macros\n"
                "The following macros are CALLed but their parameter signatures "
                "could not be found. Be extra careful with CALL parameters:\n"
                + "\n".join(f"- `{m}`" for m in analysis.unresolved_macros)
            )

        # ══════════════════════════════════════════════════════════
        # PHASE 2 + 3: GENERATE → COMPILE LOOP
        # ══════════════════════════════════════════════════════════

        # Prepare sandbox
        source_name = source_p.name or "current.xml"
        output_name = Path(output_path).name or "current.gsm"

        prev_error: Optional[str] = None
        prev_xml: Optional[str] = None
        history: list[AttemptRecord] = []
        total_tokens = 0

        for attempt in range(1, max_iter + 1):
            self.on_event("attempt_start", attempt=attempt, max_attempts=max_iter)
            attempt_start = time.monotonic()

            # Prepare sandbox paths for this attempt
            sandbox_paths = self.sandbox.prepare(source_name, output_name, attempt)

            # ── GENERATE: Build messages with focused context ──
            messages = self._build_messages(
                system_prompt=system_prompt,
                instruction=instruction,
                xml_content=focused_xml,  # v0.3: focused, not full
                full_xml_content=xml_content,  # Keep full for write-back
                error=prev_error,
                previous_code=prev_xml,
                attempt=attempt,
                max_attempts=max_iter,
            )

            self.on_event("llm_call", attempt=attempt)
            try:
                response = self.llm.generate(messages)
            except Exception as e:
                self.on_event("llm_error", error=str(e))
                history.append(AttemptRecord(
                    attempt=attempt, stage="llm_call", success=False, error=str(e)
                ))
                prev_error = f"LLM call failed: {e}"
                continue

            total_tokens += response.usage.get("total_tokens", 0)

            # Extract XML from response
            new_xml = self._extract_xml(response.content)
            if not new_xml:
                self.on_event("xml_extract_failed", attempt=attempt)
                history.append(AttemptRecord(
                    attempt=attempt, stage="xml_extraction", success=False,
                    error="Could not extract valid XML from LLM response"
                ))
                prev_error = "Failed to extract XML. Please output complete XML."
                prev_xml = response.content
                continue

            # Diff check
            if self.config.agent.diff_check and prev_xml and contents_identical(new_xml, prev_xml):
                self.on_event("identical_retry", attempt=attempt)
                duration = int((time.monotonic() - attempt_start) * 1000)
                history.append(AttemptRecord(
                    attempt=attempt, stage="diff_check", success=False,
                    error="Identical to previous attempt", duration_ms=duration,
                ))
                total_duration = int((time.monotonic() - start_time) * 1000)
                return AgentResult(
                    status=Status.FAILED, attempts=attempt,
                    error_summary="Agent produced identical code twice.",
                    history=history, total_tokens=total_tokens,
                    total_duration_ms=total_duration, analysis=analysis,
                )

            # ── SELF-REVIEW: Ask LLM to check its own output ──
            if self.self_review and self._review_prompt and attempt == 1:
                review_result = self._run_self_review(new_xml, system_prompt)
                total_tokens += review_result.get("tokens", 0)
                if review_result.get("corrected_xml"):
                    self.on_event("self_review_correction", attempt=attempt)
                    new_xml = review_result["corrected_xml"]
                elif review_result.get("passed"):
                    self.on_event("self_review_passed", attempt=attempt)

            # ── VALIDATE ──
            if self.config.agent.validate_xml:
                xml_result = validate_xml(new_xml)
                if not xml_result.valid:
                    self.on_event("xml_invalid", attempt=attempt, error=xml_result.error)
                    history.append(AttemptRecord(
                        attempt=attempt, stage="xml_validation", success=False,
                        error=xml_result.error,
                    ))
                    prev_error = f"XML not well-formed: {xml_result.error}"
                    prev_xml = new_xml
                    self.sandbox.archive_attempt(sandbox_paths)
                    continue

                gdl_issues = validate_gdl_structure(new_xml)
                if gdl_issues:
                    self.on_event("gdl_issues", attempt=attempt, issues=gdl_issues)
                    history.append(AttemptRecord(
                        attempt=attempt, stage="gdl_validation", success=False,
                        error="; ".join(gdl_issues),
                    ))
                    prev_error = "GDL issues:\n" + "\n".join(f"- {i}" for i in gdl_issues)
                    prev_xml = new_xml
                    self.sandbox.archive_attempt(sandbox_paths)
                    continue

            self.on_event("validation_passed", attempt=attempt)

            # Compute diff
            diff = compute_diff(xml_content, new_xml) if xml_content else ""

            # ── COMPILE: Write to sandbox, NOT source ──
            write_content = new_xml
            if self.debug_mode:
                write_content = inject_debug_anchors(new_xml)
                self.on_event("debug_anchors_injected", attempt=attempt)

            # v0.3: Write to temp, not source
            self.sandbox.write_temp(sandbox_paths, write_content)
            self.on_event("sandbox_written", path=str(sandbox_paths.temp_xml))

            self.on_event("compile_start", attempt=attempt)
            compile_result = self.compiler.compile(
                str(sandbox_paths.temp_xml),
                str(sandbox_paths.temp_output),
            )
            duration = int((time.monotonic() - attempt_start) * 1000)

            if compile_result.success:
                # v0.3: Promote sandbox → source + output
                self.sandbox.promote(sandbox_paths)
                self.sandbox.cleanup()
                self.on_event("compile_success", attempt=attempt,
                              output=str(sandbox_paths.final_output), duration_ms=duration)
                history.append(AttemptRecord(
                    attempt=attempt, stage="compile", success=True,
                    diff=diff, duration_ms=duration,
                ))
                total_duration = int((time.monotonic() - start_time) * 1000)
                return AgentResult(
                    status=Status.SUCCESS, attempts=attempt,
                    output_path=str(sandbox_paths.final_output),
                    history=history, total_tokens=total_tokens,
                    total_duration_ms=total_duration, analysis=analysis,
                )

            # Compile failed → archive attempt, continue
            error_msg = compile_result.stderr or compile_result.stdout or "Unknown error"
            self.on_event("compile_failed", attempt=attempt, error=error_msg)
            self.sandbox.archive_attempt(sandbox_paths)
            history.append(AttemptRecord(
                attempt=attempt, stage="compile", success=False,
                error=error_msg, diff=diff, duration_ms=duration,
            ))
            prev_error = error_msg
            prev_xml = new_xml

        # Exhausted
        self.sandbox.cleanup()
        total_duration = int((time.monotonic() - start_time) * 1000)
        self.on_event("exhausted", max_attempts=max_iter, last_error=prev_error)
        return AgentResult(
            status=Status.EXHAUSTED, attempts=max_iter,
            error_summary=prev_error or "Unknown error",
            history=history, total_tokens=total_tokens,
            total_duration_ms=total_duration, analysis=analysis,
        )

    # ── Self-Review ───────────────────────────────────────────────────

    def _run_self_review(self, xml: str, system_prompt: str) -> dict:
        """
        Ask the LLM to review its own generated code for logical errors.

        Returns dict with:
          - passed: bool
          - corrected_xml: Optional[str] (if LLM found and fixed issues)
          - tokens: int
        """
        if not self._review_prompt:
            return {"passed": True, "tokens": 0}

        review_msg = self._review_prompt.replace("{generated_xml}", xml)
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=review_msg),
        ]

        try:
            response = self.llm.generate(messages)
        except Exception:
            return {"passed": True, "tokens": 0}  # Skip review on error

        tokens = response.usage.get("total_tokens", 0)
        content = response.content.strip()

        if content.upper().startswith("LGTM"):
            return {"passed": True, "tokens": tokens}

        # Try to extract corrected XML
        corrected = self._extract_xml(content)
        if corrected:
            return {"passed": False, "corrected_xml": corrected, "tokens": tokens}

        return {"passed": True, "tokens": tokens}

    # ── Message Building ──────────────────────────────────────────────

    def _build_messages(
        self,
        system_prompt: str,
        instruction: str,
        xml_content: str,      # Focused (sliced) content for first attempt
        full_xml_content: str,  # Full content for reference
        error: Optional[str],
        previous_code: Optional[str],
        attempt: int,
        max_attempts: int,
    ) -> list[Message]:
        messages = [Message(role="system", content=system_prompt)]

        if attempt == 1:
            user_content = f"## Task\n\n{instruction}\n"
            if xml_content:
                user_content += f"\n## Current XML Source\n\n```xml\n{xml_content}\n```\n"
                # If context was sliced, remind LLM to output FULL XML
                if xml_content != full_xml_content and full_xml_content:
                    user_content += (
                        "\n**Note:** The above shows only the sections relevant to your task. "
                        "However, you MUST output the COMPLETE XML file including ALL sections "
                        "(even those not shown). Preserve all existing sections unchanged.\n"
                    )
            else:
                user_content += "\n## Note\n\nNew file. Generate complete XML from scratch.\n"
            messages.append(Message(role="user", content=user_content))
        else:
            user_content = self._error_prompt.format(
                error=error or "Unknown error",
                attempt=attempt,
                max_attempts=max_attempts,
                previous_code=previous_code or "(not available)",
            )
            messages.append(Message(role="user", content=user_content))

        return messages

    # ── XML Extraction ────────────────────────────────────────────────

    def _extract_xml(self, response: str) -> Optional[str]:
        fence_pattern = r"```(?:xml)?\s*\n(.*?)```"
        matches = re.findall(fence_pattern, response, re.DOTALL)
        for match in matches:
            match = match.strip()
            if match.startswith("<?xml") or match.startswith("<Symbol"):
                return match

        xml_pattern = r"(<\?xml.*?</Symbol>)"
        match = re.search(xml_pattern, response, re.DOTALL)
        if match:
            return match.group(1)

        symbol_pattern = r"(<Symbol>.*?</Symbol>)"
        match = re.search(symbol_pattern, response, re.DOTALL)
        if match:
            return '<?xml version="1.0" encoding="UTF-8"?>\n' + match.group(1)

        stripped = response.strip()
        if stripped.startswith("<?xml") or stripped.startswith("<Symbol"):
            return stripped

        return None
