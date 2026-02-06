"""
LP_XMLConverter wrapper.

Handles compilation of GDL XML source into .gsm/.lcf library parts,
and decompilation of .gsm back to XML for inspection.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gdl_agent.config import CompilerConfig


@dataclass
class CompileResult:
    """Result of a compilation attempt."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: int = 0
    output_path: str = ""
    command: str = ""

    @property
    def error_summary(self) -> str:
        """Extract a concise error summary from stderr."""
        if not self.stderr:
            return ""
        lines = [l.strip() for l in self.stderr.strip().splitlines() if l.strip()]
        # Return first 5 non-empty lines
        return "\n".join(lines[:5])


class Compiler:
    """
    Wrapper around LP_XMLConverter for compiling GDL XML to .gsm files.

    Usage:
        compiler = Compiler(config)
        result = compiler.compile("src/window/", "output/window.gsm")
        if result.success:
            print(f"Built: {result.output_path}")
        else:
            print(f"Error: {result.error_summary}")
    """

    def __init__(self, config: CompilerConfig):
        self.config = config

    @property
    def converter_path(self) -> Optional[str]:
        return self.config.path

    def is_available(self) -> bool:
        """Check if LP_XMLConverter is accessible."""
        if not self.converter_path:
            return False
        return Path(self.converter_path).is_file()

    def compile(self, source: str, output: str) -> CompileResult:
        """
        Compile GDL XML source to a library part.

        Args:
            source: Path to the XML source directory or file.
            output: Path for the output .gsm file.

        Returns:
            CompileResult with success status and any error information.
        """
        if not self.is_available():
            return CompileResult(
                success=False,
                exit_code=-1,
                stderr=(
                    f"LP_XMLConverter not found at: {self.converter_path}\n"
                    "Please install ArchiCAD or set CONVERTER_PATH in your environment."
                ),
            )

        # Ensure output directory exists
        Path(output).parent.mkdir(parents=True, exist_ok=True)

        cmd = [self.converter_path, "xml2libpart", source, output]
        cmd_str = " ".join(cmd)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=Path(source).parent if Path(source).is_file() else None,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            return CompileResult(
                success=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                output_path=output if proc.returncode == 0 else "",
                command=cmd_str,
            )

        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False,
                exit_code=-2,
                stderr=f"Compilation timed out after {self.config.timeout}s",
                command=cmd_str,
            )
        except OSError as e:
            return CompileResult(
                success=False,
                exit_code=-3,
                stderr=f"Failed to execute LP_XMLConverter: {e}",
                command=cmd_str,
            )

    def decompile(self, gsm_path: str, output_dir: str) -> CompileResult:
        """
        Decompile a .gsm file back to XML source.

        Args:
            gsm_path: Path to the .gsm library part.
            output_dir: Directory to extract XML source into.

        Returns:
            CompileResult with success status.
        """
        if not self.is_available():
            return CompileResult(
                success=False,
                exit_code=-1,
                stderr="LP_XMLConverter not found.",
            )

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        cmd = [self.converter_path, "libpart2xml", gsm_path, output_dir]
        cmd_str = " ".join(cmd)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            return CompileResult(
                success=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                output_path=output_dir if proc.returncode == 0 else "",
                command=cmd_str,
            )

        except (subprocess.TimeoutExpired, OSError) as e:
            return CompileResult(
                success=False,
                exit_code=-3,
                stderr=str(e),
                command=cmd_str,
            )


class MockCompiler:
    """
    Mock compiler for testing without ArchiCAD.

    Validates XML structure and simulates common GDL compile errors.
    """

    def __init__(self, fail_pattern: Optional[str] = None):
        """
        Args:
            fail_pattern: If set, compilation fails when this pattern is found in the XML.
        """
        self.fail_pattern = fail_pattern
        self.compile_count = 0

    def is_available(self) -> bool:
        return True

    def compile(self, source: str, output: str) -> CompileResult:
        self.compile_count += 1

        # Read source
        source_path = Path(source)
        if not source_path.exists():
            return CompileResult(success=False, exit_code=1, stderr=f"File not found: {source}")

        content = source_path.read_text(encoding="utf-8")

        # Basic XML validation
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return CompileResult(success=False, exit_code=1, stderr=f"XML Parse Error: {e}")

        # Check for fail pattern
        if self.fail_pattern and self.fail_pattern in content:
            return CompileResult(
                success=False,
                exit_code=1,
                stderr=f"GDL Error: Pattern check failed for '{self.fail_pattern}'",
            )

        # Check GDL structure
        errors = []
        if root.tag != "Symbol":
            errors.append(f"Root element must be 'Symbol', got '{root.tag}'")

        script_3d = root.find(".//Script_3D")
        if script_3d is not None and script_3d.text:
            import re

            script = script_3d.text
            if_count = len(re.findall(r"\bIF\b", script, re.IGNORECASE))
            endif_count = len(re.findall(r"\bENDIF\b", script, re.IGNORECASE))
            if if_count != endif_count:
                errors.append(
                    f"Mismatched IF/ENDIF (IF: {if_count}, ENDIF: {endif_count})"
                )

        if errors:
            return CompileResult(
                success=False, exit_code=1, stderr="\n".join(errors)
            )

        # Success - write mock output
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(f"[mock-gsm] from {source}", encoding="utf-8")

        return CompileResult(
            success=True, exit_code=0,
            stdout=f"Compiled: {output}",
            output_path=output,
        )

    def decompile(self, gsm_path: str, output_dir: str) -> CompileResult:
        return CompileResult(success=False, stderr="Mock compiler does not support decompile")
