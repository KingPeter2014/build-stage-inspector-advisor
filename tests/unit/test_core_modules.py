"""
tests/unit/test_core_modules.py
Unit tests for: cleaner, prompt registry, RBAC, cost manager, audit logger.
"""
import pytest
import tempfile
import os
from datetime import date

# ── Cleaner ────────────────────────────────────────────────────────────────────
from data_ingestion.etl.cleaner import DocumentCleaner, clean_text, detect_and_redact_pii
from data_ingestion.sources.base import RawDocument


class TestCleaner:
    def _make_doc(self, content: str) -> RawDocument:
        return RawDocument(id="test-1", content=content, source="test", source_type="unstructured")

    def test_clean_text_collapses_whitespace(self):
        assert clean_text("hello   world") == "hello world"

    def test_clean_text_removes_control_chars(self):
        assert "\x00" not in clean_text("hello\x00world")

    def test_pii_email_detected_and_redacted(self):
        text, detected = detect_and_redact_pii("Contact: user@example.com for info")
        assert "email" in detected
        assert "user@example.com" not in text
        assert "[EMAIL_REDACTED]" in text

    def test_pii_ssn_detected(self):
        _, detected = detect_and_redact_pii("SSN: 123-45-6789")
        assert "ssn" in detected

    def test_cleaner_drops_short_docs(self):
        cleaner = DocumentCleaner(min_length=100)
        result = cleaner.process(self._make_doc("too short"))
        assert result is None

    def test_cleaner_returns_cleaned_doc(self):
        cleaner = DocumentCleaner(min_length=10)
        result = cleaner.process(self._make_doc("This is a valid document with enough content."))
        assert result is not None
        assert result.content.strip() != ""


# ── Prompt Registry ────────────────────────────────────────────────────────────
from storage.prompt_registry.registry import LocalPromptRegistry, PromptVersion


class TestPromptRegistry:
    def test_push_and_get_latest(self, tmp_path):
        registry = LocalPromptRegistry(str(tmp_path / "prompts.json"))
        pv = PromptVersion(name="test_prompt", version=0, template="Hello {{ name }}")
        pushed = registry.push(pv)
        retrieved = registry.get("test_prompt")
        assert retrieved.template == "Hello {{ name }}"
        assert retrieved.version == 1

    def test_version_increments(self, tmp_path):
        registry = LocalPromptRegistry(str(tmp_path / "prompts.json"))
        for _ in range(3):
            registry.push(PromptVersion(name="my_prompt", version=0, template="v{{ n }}"))
        versions = registry.list_versions("my_prompt")
        assert len(versions) == 3
        assert versions[-1].version == 3

    def test_prompt_render(self):
        pv = PromptVersion(name="qa", version=1, template="Answer: {{ question }}")
        rendered = pv.render(question="What is LLMOps?")
        assert "What is LLMOps?" in rendered

    def test_missing_prompt_raises(self, tmp_path):
        registry = LocalPromptRegistry(str(tmp_path / "prompts.json"))
        with pytest.raises(KeyError):
            registry.get("nonexistent")


# ── RBAC ───────────────────────────────────────────────────────────────────────
from governance.access_control.rbac import RBACEnforcer, User, Role, AccessDenied


class TestRBAC:
    def setup_method(self):
        self.enforcer = RBACEnforcer()

    def test_viewer_can_query(self):
        user = User(id="u1", role=Role.VIEWER)
        assert self.enforcer.check(user, "chat:completion") is True

    def test_viewer_cannot_deploy(self):
        user = User(id="u1", role=Role.VIEWER)
        assert self.enforcer.check(user, "model:deploy") is False

    def test_admin_can_do_everything(self):
        user = User(id="u1", role=Role.ADMIN)
        for perm in ["chat:completion", "model:deploy", "audit:read", "model:fine_tune"]:
            assert self.enforcer.check(user, perm) is True

    def test_enforce_raises_on_denial(self):
        user = User(id="u1", role=Role.VIEWER)
        with pytest.raises(AccessDenied):
            self.enforcer.enforce(user, "model:deploy")

    def test_model_allowlist_enforced(self):
        user = User(id="u1", role=Role.DEVELOPER, model_allowlist=["gpt-4o"])
        assert self.enforcer.check_model_access(user, "gpt-4o") is True
        assert self.enforcer.check_model_access(user, "claude-opus-4-5") is False

    def test_empty_allowlist_allows_all(self):
        user = User(id="u1", role=Role.DEVELOPER, model_allowlist=[])
        assert self.enforcer.check_model_access(user, "any-model") is True


# ── Cost Manager ───────────────────────────────────────────────────────────────
from governance.cost.cost_manager import CostManager, CostRecord, BudgetPolicy


class TestCostManager:
    def test_record_and_daily_spend(self, tmp_path):
        manager = CostManager(ledger_path=str(tmp_path / "ledger.jsonl"))
        from datetime import datetime
        record = CostRecord(
            timestamp=datetime.utcnow().isoformat(),
            user_id="u1", team_id="team-a", model="gpt-4o",
            prompt_tokens=100, completion_tokens=50, cost_usd=0.05,
        )
        manager.record(record)
        assert manager.daily_spend("team-a") == pytest.approx(0.05)

    def test_budget_check_blocks_over_limit(self, tmp_path):
        manager = CostManager(ledger_path=str(tmp_path / "ledger.jsonl"))
        manager.register_policy(BudgetPolicy(team_id="team-b", per_request_limit_usd=0.01))
        result = manager.check_budget("team-b", estimated_cost=0.05)
        assert result["allowed"] is False
        assert "per_request_limit_exceeded" in result["reason"]

    def test_budget_check_allows_within_limit(self, tmp_path):
        manager = CostManager(ledger_path=str(tmp_path / "ledger.jsonl"))
        manager.register_policy(BudgetPolicy(team_id="team-c", per_request_limit_usd=1.0, daily_limit_usd=100.0))
        result = manager.check_budget("team-c", estimated_cost=0.05)
        assert result["allowed"] is True


# ── Audit Logger ───────────────────────────────────────────────────────────────
from governance.audit.audit_logger import AuditLogger, AuditConfig


class TestAuditLogger:
    def test_log_and_verify_integrity(self, tmp_path):
        config = AuditConfig(log_path=str(tmp_path / "audit.jsonl"), redact_pii=False)
        logger = AuditLogger(config)
        logger.log("chat_completion", "gpt-4o", "What is RAG?", "RAG stands for...", user_id="u1")
        valid, tampered = logger.verify_log_integrity()
        assert valid == 1
        assert tampered == 0

    def test_multiple_entries_all_valid(self, tmp_path):
        config = AuditConfig(log_path=str(tmp_path / "audit.jsonl"))
        logger = AuditLogger(config)
        for i in range(5):
            logger.log("rag_query", "gpt-4o", f"question {i}", f"answer {i}")
        valid, tampered = logger.verify_log_integrity()
        assert valid == 5
        assert tampered == 0

    def test_entry_hash_is_deterministic(self):
        from governance.audit.audit_logger import AuditEntry
        entry = AuditEntry(action="test", model="gpt-4o", user_id="u1")
        entry.finalise()
        original_hash = entry.entry_hash
        assert entry.verify() is True
