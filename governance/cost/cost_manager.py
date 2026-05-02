"""
governance/cost/cost_manager.py
Token budgeting, cost allocation per team/user, and spend alerting.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any


@dataclass
class CostRecord:
    timestamp: str
    user_id: str
    team_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


@dataclass
class BudgetPolicy:
    team_id: str
    daily_limit_usd: float = 50.0
    monthly_limit_usd: float = 1000.0
    per_request_limit_usd: float = 1.0
    alert_threshold: float = 0.8          # Alert at 80% of limit


class CostManager:
    def __init__(self, ledger_path: str = "data/cost_ledger.jsonl"):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._policies: dict[str, BudgetPolicy] = {}

    def register_policy(self, policy: BudgetPolicy) -> None:
        self._policies[policy.team_id] = policy

    def record(self, record: CostRecord) -> None:
        with self.ledger_path.open("a") as f:
            f.write(json.dumps(record.__dict__) + "\n")

    def _load_records(self) -> list[CostRecord]:
        if not self.ledger_path.exists():
            return []
        records = []
        for line in self.ledger_path.read_text().splitlines():
            if line.strip():
                records.append(CostRecord(**json.loads(line)))
        return records

    def daily_spend(self, team_id: str, on_date: date | None = None) -> float:
        target = (on_date or date.today()).isoformat()
        return sum(
            r.cost_usd for r in self._load_records()
            if r.team_id == team_id and r.timestamp.startswith(target)
        )

    def monthly_spend(self, team_id: str, year: int | None = None, month: int | None = None) -> float:
        now = datetime.utcnow()
        prefix = f"{year or now.year}-{(month or now.month):02d}"
        return sum(
            r.cost_usd for r in self._load_records()
            if r.team_id == team_id and r.timestamp.startswith(prefix)
        )

    def check_budget(self, team_id: str, estimated_cost: float) -> dict[str, Any]:
        policy = self._policies.get(team_id)
        if not policy:
            return {"allowed": True, "reason": "no_policy"}

        if estimated_cost > policy.per_request_limit_usd:
            return {"allowed": False, "reason": "per_request_limit_exceeded",
                    "limit": policy.per_request_limit_usd, "estimated": estimated_cost}

        daily = self.daily_spend(team_id)
        if daily + estimated_cost > policy.daily_limit_usd:
            return {"allowed": False, "reason": "daily_limit_exceeded",
                    "limit": policy.daily_limit_usd, "current": daily}

        monthly = self.monthly_spend(team_id)
        if monthly + estimated_cost > policy.monthly_limit_usd:
            return {"allowed": False, "reason": "monthly_limit_exceeded",
                    "limit": policy.monthly_limit_usd, "current": monthly}

        alerts = []
        if daily / policy.daily_limit_usd >= policy.alert_threshold:
            alerts.append(f"Daily spend at {daily/policy.daily_limit_usd:.0%} of limit")

        return {"allowed": True, "alerts": alerts, "daily_spend": daily, "monthly_spend": monthly}

    def team_summary(self, team_id: str) -> dict[str, Any]:
        records = [r for r in self._load_records() if r.team_id == team_id]
        by_model: dict[str, float] = {}
        for r in records:
            by_model[r.model] = by_model.get(r.model, 0.0) + r.cost_usd
        return {
            "team_id": team_id,
            "total_requests": len(records),
            "total_cost_usd": sum(r.cost_usd for r in records),
            "cost_by_model": by_model,
            "daily_spend": self.daily_spend(team_id),
            "monthly_spend": self.monthly_spend(team_id),
        }
