"""Tests for AnalysisContext, DataSchema, and ConversationMemory."""

import pandas as pd
import numpy as np
import pytest

from app.agent.specialists.context import AnalysisContext, DataSchema, ColumnProfile
from app.agent.memory import ConversationMemory


# ─── AnalysisContext ──────────────────────────────────────────────────────────

class TestAnalysisContext:
    def test_fresh_context(self):
        ctx = AnalysisContext()
        assert not ctx.has_data
        assert ctx.dataset_ids == []
        assert ctx.get_dataset_summaries() == "No datasets loaded."

    def test_add_dataset(self, sample_df):
        ctx = AnalysisContext()
        schema = ctx.add_dataset("test", sample_df, "test.csv")
        assert ctx.has_data
        assert "test" in ctx.dataset_ids
        assert schema.row_count == 100
        assert schema.column_count == 6

    def test_schema_column_profiles(self, sample_df):
        ctx = AnalysisContext()
        schema = ctx.add_dataset("test", sample_df, "test.csv")
        assert len(schema.columns) == 6
        for col in schema.columns:
            assert isinstance(col, ColumnProfile)
            assert col.name
            assert col.dtype

    def test_add_result(self):
        ctx = AnalysisContext()
        ctx.add_result("eda", "Profiled dataset", "table", {"rows": 100})
        assert len(ctx.results) == 1
        assert ctx.results[0].specialist_name == "eda"

    def test_variables(self):
        ctx = AnalysisContext()
        ctx.set_variable("test_var", [1, 2, 3])
        assert ctx.get_variable("test_var") == [1, 2, 3]
        assert ctx.get_variable("nonexistent", "default") == "default"

    def test_get_dataset_summaries(self, sample_df):
        ctx = AnalysisContext()
        ctx.add_dataset("test", sample_df, "test.csv")
        summary = ctx.get_dataset_summaries()
        assert "test.csv" in summary
        assert "100 rows" in summary

    def test_get_recent_results_summary(self):
        ctx = AnalysisContext()
        assert ctx.get_recent_results_summary() == "No analysis results yet."
        ctx.add_result("eda", "Profiled", "table", {"rows": 100})
        summary = ctx.get_recent_results_summary()
        assert "eda" in summary
        assert "Profiled" in summary

    def test_recent_results_limit(self):
        ctx = AnalysisContext()
        for i in range(20):
            ctx.add_result("eda", f"Step {i}", "table", None)
        summary = ctx.get_recent_results_summary(limit=5)
        assert "Step 19" in summary
        assert "Step 10" not in summary

    def test_multiple_datasets(self, sample_df):
        ctx = AnalysisContext()
        ctx.add_dataset("ds1", sample_df, "data1.csv")
        ctx.add_dataset("ds2", sample_df.head(10), "data2.csv")
        assert len(ctx.dataset_ids) == 2
        assert ctx.schemas["ds2"].row_count == 10

    def test_schema_to_summary(self, sample_df):
        ctx = AnalysisContext()
        schema = ctx.add_dataset("test", sample_df, "test.csv")
        summary = schema.to_summary()
        assert "test.csv" in summary
        assert "100 rows" in summary
        assert "6 columns" in summary

    def test_null_column_profiles(self):
        df = pd.DataFrame({"good": [1, 2, 3], "bad": [None, None, None]})
        ctx = AnalysisContext()
        schema = ctx.add_dataset("nulls", df, "nulls.csv")
        bad_col = next(c for c in schema.columns if c.name == "bad")
        assert bad_col.null_count == 3
        assert bad_col.null_pct == 100.0

    def test_session_id_generated(self):
        ctx1 = AnalysisContext()
        ctx2 = AnalysisContext()
        assert ctx1.session_id != ctx2.session_id


# ─── ConversationMemory ──────────────────────────────────────────────────────

class TestConversationMemory:
    def test_empty_memory(self):
        mem = ConversationMemory()
        assert mem.is_empty
        assert mem.message_count == 0
        assert mem.get_messages() == []

    def test_add_user_message(self):
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        assert mem.message_count == 1
        msgs = mem.get_messages()
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"

    def test_add_assistant_message(self):
        mem = ConversationMemory()
        mem.add_assistant_message("Hi there")
        msgs = mem.get_messages()
        assert msgs[0]["role"] == "assistant"

    def test_conversation_flow(self):
        mem = ConversationMemory()
        mem.add_user_message("What are trends?")
        mem.add_assistant_message("Revenue is up 15%.")
        mem.add_user_message("Why?")
        assert mem.message_count == 3

    def test_tool_result(self):
        mem = ConversationMemory()
        mem.add_tool_result("tool_123", "Profile complete: 100 rows")
        msgs = mem.get_messages()
        assert msgs[0]["role"] == "user"
        content = msgs[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "tool_123"

    def test_tool_results_batch(self):
        mem = ConversationMemory()
        mem.add_tool_results_batch([
            {"tool_use_id": "t1", "content": "Result 1"},
            {"tool_use_id": "t2", "content": "Result 2"},
        ])
        msgs = mem.get_messages()
        assert len(msgs) == 1
        assert len(msgs[0]["content"]) == 2

    def test_sliding_window_trim(self):
        mem = ConversationMemory(max_messages=5)
        for i in range(10):
            mem.add_user_message(f"Message {i}")
        assert mem.message_count == 5
        msgs = mem.get_messages()
        assert msgs[0]["content"] == "Message 5"

    def test_get_last_n(self):
        mem = ConversationMemory()
        for i in range(5):
            mem.add_user_message(f"Msg {i}")
        last2 = mem.get_last_n(2)
        assert len(last2) == 2
        assert last2[0]["content"] == "Msg 3"

    def test_clear(self):
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi")
        mem.clear()
        assert mem.is_empty
        assert mem.message_count == 0
