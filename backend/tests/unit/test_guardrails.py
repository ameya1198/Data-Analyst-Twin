"""Tests for guardrails: validator, sanitizer, rate limiter, confirmation."""

import asyncio

import pytest

from app.guardrails.validator import InputValidator, ValidationResult
from app.guardrails.sanitizer import OutputSanitizer
from app.guardrails.rate_limiter import RateLimiter
from app.guardrails.confirmation import ConfirmationManager, ConfirmationRequest, ConfirmationResponse


# ─── InputValidator ───────────────────────────────────────────────────────────

class TestInputValidator:
    @pytest.fixture
    def validator(self):
        return InputValidator()

    def test_valid_message(self, validator):
        result = validator.validate_message("What are the trends in sales?")
        assert result.valid

    def test_empty_message(self, validator):
        result = validator.validate_message("")
        assert not result.valid
        assert "empty" in result.error.lower()

    def test_whitespace_only_message(self, validator):
        result = validator.validate_message("   ")
        assert not result.valid

    def test_too_long_message(self, validator):
        result = validator.validate_message("x" * 20_000)
        assert not result.valid
        assert "too long" in result.error.lower()

    def test_valid_file_upload(self, validator):
        result = validator.validate_file_upload("data.csv", 1024)
        assert result.valid

    def test_invalid_file_type(self, validator):
        result = validator.validate_file_upload("virus.exe", 1024)
        assert not result.valid
        assert "not allowed" in result.error.lower()

    def test_file_too_large(self, validator):
        size = 200 * 1024 * 1024  # 200MB
        result = validator.validate_file_upload("big.csv", size)
        assert not result.valid
        assert "too large" in result.error.lower()

    def test_no_filename(self, validator):
        result = validator.validate_file_upload("", 1024)
        assert not result.valid

    def test_valid_tool_params(self, validator):
        result = validator.validate_tool_params("eda_profile", {"dataset_id": "abc"})
        assert result.valid

    def test_tool_param_too_long(self, validator):
        result = validator.validate_tool_params("eda_profile", {"x": "a" * 10_000})
        assert not result.valid

    @pytest.mark.parametrize("ext", ["csv", "xlsx", "xls", "json", "parquet"])
    def test_allowed_file_types(self, validator, ext):
        result = validator.validate_file_upload(f"data.{ext}", 1024)
        assert result.valid

    def test_validation_result_ok(self):
        r = ValidationResult.ok()
        assert r.valid
        assert r.error is None

    def test_validation_result_fail(self):
        r = ValidationResult.fail("bad input")
        assert not r.valid
        assert r.error == "bad input"


# ─── OutputSanitizer ──────────────────────────────────────────────────────────

class TestOutputSanitizer:
    @pytest.fixture
    def sanitizer(self):
        return OutputSanitizer()

    def test_clean_text_passes_through(self, sanitizer):
        text = "Revenue is $1.2M, up 15% QoQ."
        assert sanitizer.sanitize_text(text) == text

    def test_redacts_anthropic_key(self, sanitizer):
        text = "Found key sk-ant-api03-aBcDeFgHiJkLmNoPqRsTuVwXyZ in config"
        result = sanitizer.sanitize_text(text)
        assert "[REDACTED]" in result
        assert "sk-ant" not in result

    def test_redacts_openai_key(self, sanitizer):
        text = "Key is sk-1234567890abcdefghijklmnop"
        result = sanitizer.sanitize_text(text)
        assert "[REDACTED]" in result

    def test_redacts_aws_key(self, sanitizer):
        text = "AWS key AKIAIOSFODNN7EXAMPLE found"
        result = sanitizer.sanitize_text(text)
        assert "[REDACTED]" in result

    def test_redacts_password(self, sanitizer):
        text = 'Config: password = "super_secret_123"'
        result = sanitizer.sanitize_text(text)
        assert "[REDACTED]" in result
        assert "super_secret" not in result

    def test_safe_code_passes(self, sanitizer):
        code = "import pandas as pd\ndf = pd.read_csv('data.csv')\nprint(df.head())"
        is_safe, _ = sanitizer.validate_generated_code(code)
        assert is_safe

    def test_blocks_os_system(self, sanitizer):
        code = "import os\nos.system('rm -rf /')"
        is_safe, reason = sanitizer.validate_generated_code(code)
        assert not is_safe
        assert "dangerous" in reason.lower() or "os.system" in reason

    def test_blocks_subprocess(self, sanitizer):
        code = "import subprocess\nsubprocess.run(['ls'])"
        is_safe, _ = sanitizer.validate_generated_code(code)
        assert not is_safe

    def test_blocks_eval(self, sanitizer):
        code = "result = eval(user_input)"
        is_safe, _ = sanitizer.validate_generated_code(code)
        assert not is_safe

    def test_blocks_exec(self, sanitizer):
        code = "exec(malicious_code)"
        is_safe, _ = sanitizer.validate_generated_code(code)
        assert not is_safe

    def test_blocks_dunder_import(self, sanitizer):
        code = "__import__('os').system('whoami')"
        is_safe, _ = sanitizer.validate_generated_code(code)
        assert not is_safe

    def test_allowed_imports_pass(self, sanitizer):
        code = "import pandas as pd\nimport numpy as np\nfrom scipy import stats"
        is_ok, disallowed = sanitizer.check_imports(code)
        assert is_ok
        assert disallowed == []

    def test_disallowed_imports_flagged(self, sanitizer):
        code = "import os\nimport socket\nimport pandas"
        is_ok, disallowed = sanitizer.check_imports(code)
        assert not is_ok
        assert "os" in disallowed
        assert "socket" in disallowed

    def test_sanitize_result_dict(self, sanitizer):
        data = {"key": "sk-ant-api03-aBcDeFgHiJkLmNoPqRsTuVwXyZ", "safe": "hello"}
        result = sanitizer.sanitize_result(data)
        assert "[REDACTED]" in result["key"]
        assert result["safe"] == "hello"

    def test_sanitize_result_list(self, sanitizer):
        data = ["safe", "sk-ant-api03-aBcDeFgHiJkLmNoPqRsTuVwXyZ"]
        result = sanitizer.sanitize_result(data)
        assert result[0] == "safe"
        assert "[REDACTED]" in result[1]

    def test_sanitize_result_passthrough(self, sanitizer):
        assert sanitizer.sanitize_result(42) == 42
        assert sanitizer.sanitize_result(None) is None


# ─── RateLimiter ──────────────────────────────────────────────────────────────

class TestRateLimiter:
    @pytest.fixture
    def limiter(self):
        return RateLimiter(max_llm_calls=5, max_specialist_calls_per_turn=3)

    def test_initial_calls_allowed(self, limiter):
        result = limiter.check_llm_call("sess1")
        assert result.allowed
        assert result.remaining == 5

    def test_llm_limit_enforced(self, limiter):
        for _ in range(5):
            limiter.record_llm_call("sess1")
        result = limiter.check_llm_call("sess1")
        assert not result.allowed
        assert "limit reached" in result.reason.lower()

    def test_specialist_limit_enforced(self, limiter):
        for _ in range(3):
            limiter.record_specialist_call("sess1")
        result = limiter.check_specialist_call("sess1")
        assert not result.allowed

    def test_new_turn_resets_specialist_count(self, limiter):
        for _ in range(3):
            limiter.record_specialist_call("sess1")
        limiter.new_turn("sess1")
        result = limiter.check_specialist_call("sess1")
        assert result.allowed

    def test_sessions_are_independent(self, limiter):
        for _ in range(5):
            limiter.record_llm_call("sess1")
        result = limiter.check_llm_call("sess2")
        assert result.allowed

    def test_usage_summary(self, limiter):
        limiter.record_llm_call("sess1")
        limiter.record_llm_call("sess1")
        limiter.record_specialist_call("sess1")

        summary = limiter.get_usage_summary("sess1")
        assert summary["llm_calls"] == 2
        assert summary["llm_calls_remaining"] == 3
        assert summary["specialist_calls_this_turn"] == 1
        assert summary["total_specialist_calls"] == 1

    def test_total_specialist_calls_persist_across_turns(self, limiter):
        limiter.record_specialist_call("sess1")
        limiter.record_specialist_call("sess1")
        limiter.new_turn("sess1")
        limiter.record_specialist_call("sess1")

        summary = limiter.get_usage_summary("sess1")
        assert summary["total_specialist_calls"] == 3
        assert summary["specialist_calls_this_turn"] == 1


# ─── ConfirmationManager ─────────────────────────────────────────────────────

class TestConfirmationManager:
    @pytest.fixture
    def manager(self):
        return ConfirmationManager(timeout_seconds=1)

    def test_needs_confirmation(self, manager):
        assert manager.needs_confirmation("data_cleaning", "clean_drop_nulls")
        assert manager.needs_confirmation("sql", "sql_execute_write")
        assert not manager.needs_confirmation("eda", "eda_profile")
        assert not manager.needs_confirmation("viz", "viz_bar_chart")

    async def test_confirmation_approved(self, manager):
        sent_requests = []

        async def mock_send(request):
            sent_requests.append(request)
            manager.resolve(request.request_id, approved=True)

        request = ConfirmationRequest(
            request_id="req1", specialist_name="data_cleaning",
            tool_name="clean_drop_nulls",
            description="Drop 50 null rows", details={}, impact="Removes 50 rows",
        )

        response = await manager.request_confirmation(request, mock_send)
        assert response.approved
        assert len(sent_requests) == 1

    async def test_confirmation_denied(self, manager):
        async def mock_send(request):
            manager.resolve(request.request_id, approved=False, message="Too risky")

        request = ConfirmationRequest(
            request_id="req2", specialist_name="sql",
            tool_name="sql_execute_write",
            description="DELETE query", details={}, impact="Deletes rows",
        )

        response = await manager.request_confirmation(request, mock_send)
        assert not response.approved
        assert response.user_message == "Too risky"

    async def test_confirmation_timeout(self, manager):
        async def mock_send(request):
            pass  # Don't resolve — triggers timeout

        request = ConfirmationRequest(
            request_id="req3", specialist_name="data_cleaning",
            tool_name="clean_drop_nulls",
            description="Drop nulls", details={}, impact="Removes rows",
        )

        response = await manager.request_confirmation(request, mock_send)
        assert not response.approved
        assert "timed out" in response.user_message.lower()

    def test_resolve_nonexistent_request(self, manager):
        result = manager.resolve("nonexistent", approved=True)
        assert result is False
