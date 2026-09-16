"""
Action Permissions, Confirmation Guardrails, and Undo Stack for Smart Home Assistant.
Provides reversible action rollback and risk categorizations (SAFE, MUTATING, HIGH_RISK).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class RiskLevel(Enum):
    SAFE = "safe"              # Read-only queries, time/weather/status
    MUTATING = "mutating"      # Timers, reminders, UI theme, memory facts
    HIGH_RISK = "high_risk"    # Deleting all data, hardware shutdown, phone calls


@dataclass
class ReversibleAction:
    action_id: str
    description: str
    undo_fn: Callable[[], bool]
    metadata: Optional[Dict[str, Any]] = None


class ActionGuardManager:
    def __init__(self):
        self.undo_stack: List[ReversibleAction] = []
        self.pending_confirmations: Dict[str, Dict[str, Any]] = {}

    def push_undo(self, action_id: str, description: str, undo_fn: Callable[[], bool], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Pushes a reversible action onto the undo stack."""
        entry = ReversibleAction(
            action_id=action_id,
            description=description,
            undo_fn=undo_fn,
            metadata=metadata or {},
        )
        self.undo_stack.append(entry)
        # Limit undo history to recent 20 actions
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def pop_and_undo(self) -> Dict[str, Any]:
        """Undoes the most recent reversible action."""
        if not self.undo_stack:
            return {"ok": False, "message": "There is nothing to undo."}

        last_action = self.undo_stack.pop()
        try:
            success = last_action.undo_fn()
            if success:
                return {
                    "ok": True,
                    "action_id": last_action.action_id,
                    "description": last_action.description,
                    "message": f"Undid: {last_action.description}.",
                }
            else:
                return {
                    "ok": False,
                    "action_id": last_action.action_id,
                    "message": f"Could not undo {last_action.description}.",
                }
        except Exception as e:
            return {
                "ok": False,
                "action_id": last_action.action_id,
                "message": f"Error while undoing: {e}",
            }

    def require_confirmation(self, action_key: str, action_desc: str, execute_fn: Callable[[], str]) -> str:
        """Registers a high-risk action requiring user voice/UI confirmation."""
        self.pending_confirmations[action_key] = {
            "description": action_desc,
            "execute_fn": execute_fn,
        }
        return f"Are you sure you want to {action_desc}? Say 'confirm' or 'yes' to proceed."

    def execute_confirmed(self, action_key: Optional[str] = None) -> Optional[str]:
        """Executes the pending confirmed action."""
        if not self.pending_confirmations:
            return None

        key = action_key or list(self.pending_confirmations.keys())[-1]
        pending = self.pending_confirmations.pop(key, None)
        if pending and "execute_fn" in pending:
            try:
                return pending["execute_fn"]()
            except Exception as e:
                return f"Failed to execute confirmed action: {e}"
        return None

    def cancel_pending(self) -> None:
        self.pending_confirmations.clear()


action_guards = ActionGuardManager()
