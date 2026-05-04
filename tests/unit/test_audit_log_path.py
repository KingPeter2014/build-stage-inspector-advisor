from governance.audit.audit_logger import AuditConfig


def test_default_audit_log_path_is_not_tracked_repo_data():
    assert AuditConfig().log_path == "artifacts/audit/audit.jsonl"
