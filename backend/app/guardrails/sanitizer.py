"""
Output sanitizer — cleans agent outputs before they reach the user.

Strips potentially sensitive information and validates generated code
before sandbox execution.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Patterns that should never appear in agent output
SENSITIVE_PATTERNS = [
    re.compile(r"sk-ant-[a-zA-Z0-9\-_]{20,}", re.IGNORECASE),   # Anthropic keys
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),           # OpenAI keys
    re.compile(r"password\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),              # AWS access keys
]

# Imports allowed in sandboxed code execution
ALLOWED_IMPORTS = {
    "pandas", "pd",
    "numpy", "np",
    "scipy", "scipy.stats",
    "statsmodels", "statsmodels.api", "statsmodels.formula.api",
    "plotly", "plotly.express", "plotly.graph_objects", "plotly.subplots",
    "math", "statistics", "collections", "itertools", "functools",
    "datetime", "json", "re",
}

# Dangerous operations that should never appear in generated code
DANGEROUS_PATTERNS = [
    re.compile(r"\bos\.(system|popen|exec|remove|rmdir|unlink)\b"),
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\b__import__\b"),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\bopen\s*\([^)]*['\"]w['\"]"),  # open() in write mode
    re.compile(r"\bshutil\.(rmtree|move|copy)\b"),
]


class OutputSanitizer:
    """Sanitizes agent outputs to prevent data leaks and unsafe code execution."""

    def sanitize_text(self, text: str) -> str:
        """Strip sensitive patterns from text output."""
        sanitized = text
        for pattern in SENSITIVE_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized

    def validate_generated_code(self, code: str) -> tuple[bool, str]:
        """
        Check if generated Python code is safe for sandbox execution.
        Returns (is_safe, reason).
        """
        for pattern in DANGEROUS_PATTERNS:
            match = pattern.search(code)
            if match:
                logger.warning(
                    "dangerous_code_blocked",
                    pattern=pattern.pattern,
                    matched=match.group(),
                )
                return False, f"Blocked dangerous operation: {match.group()}"

        return True, "Code passed safety check"

    def check_imports(self, code: str) -> tuple[bool, list[str]]:
        """Check that all imports in generated code are from the allowlist."""
        import_pattern = re.compile(
            r"^\s*(?:from\s+(\S+)|import\s+(\S+))", re.MULTILINE
        )
        disallowed = []
        for match in import_pattern.finditer(code):
            module = match.group(1) or match.group(2)
            base_module = module.split(".")[0]
            if base_module not in ALLOWED_IMPORTS and module not in ALLOWED_IMPORTS:
                disallowed.append(module)

        if disallowed:
            logger.warning("disallowed_imports", modules=disallowed)
            return False, disallowed

        return True, []

    def sanitize_result(self, data: Any) -> Any:
        """Sanitize specialist result data before streaming to the frontend."""
        if isinstance(data, str):
            return self.sanitize_text(data)
        if isinstance(data, dict):
            return {k: self.sanitize_result(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.sanitize_result(item) for item in data]
        return data
