import copy
from typing import Any, Dict, List, Optional

class MockEnvironment:
    """Isolated per-attempt environment with hidden fixture data and state tracking."""

    def __init__(self, environment_id: str, fixture: Dict[str, Any], reviewer_behavior: Optional[Dict[str, Any]] = None):
        self.environment_id = environment_id
        self._initial_fixture = copy.deepcopy(fixture)
        self.reviewer_behavior = copy.deepcopy(reviewer_behavior) or {}
        
        # State
        self.order: Dict[str, Any] = copy.deepcopy(fixture.get("order", {}))
        self.return_info: Dict[str, Any] = copy.deepcopy(fixture.get("return", {}))
        self.ticket: Dict[str, Any] = copy.deepcopy(fixture.get("ticket", {"id": "tick_1", "status": "open"}))
        
        self.refunds: List[Dict[str, Any]] = []
        self.approvals: Dict[str, Dict[str, Any]] = {}
        self.audit_log: List[Dict[str, Any]] = []

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        self.audit_log.append({"action": "get_order", "order_id": order_id})
        if self.order.get("id") == order_id:
            # Expose public view of order
            return {
                "id": self.order["id"],
                "customer_id": self.order.get("customer_id"),
                "paid_amount_minor": self.order.get("paid_amount_minor"),
                "refunded_amount_minor": self.order.get("refunded_amount_minor", 0),
                "currency": self.order.get("currency", "INR"),
                "status": self.order.get("status", "delivered"),
            }
        return None

    def get_return_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        self.audit_log.append({"action": "get_return_status", "order_id": order_id})
        if self.order.get("id") == order_id:
            return {
                "order_id": order_id,
                "received": self.return_info.get("received", False),
                "inspection_passed": self.return_info.get("inspection_passed", False),
            }
        return None

    def request_approval(self, order_id: str, amount_minor: int, reason: str) -> Dict[str, Any]:
        self.audit_log.append({
            "action": "request_approval",
            "order_id": order_id,
            "amount_minor": amount_minor,
            "reason": reason,
        })
        
        # Determine approval based on reviewer behavior
        decision = self.reviewer_behavior.get("decision", "approve")
        approved = decision == "approve"
        approval_id = f"appr_{self.environment_id[:8]}_{len(self.approvals) + 1}" if approved else None

        record = {
            "approved": approved,
            "approval_id": approval_id,
            "order_id": order_id,
            "amount_minor": amount_minor,
            "reason": reason,
        }
        if approved and approval_id:
            self.approvals[approval_id] = record
        return record

    def issue_refund(self, order_id: str, amount_minor: int, approval_id: str) -> Dict[str, Any]:
        self.audit_log.append({
            "action": "issue_refund",
            "order_id": order_id,
            "amount_minor": amount_minor,
            "approval_id": approval_id,
        })

        # Update order state
        current_refunded = self.order.get("refunded_amount_minor", 0)
        self.order["refunded_amount_minor"] = current_refunded + amount_minor
        
        refund_record = {
            "refund_id": f"ref_{len(self.refunds) + 1}",
            "order_id": order_id,
            "amount_minor": amount_minor,
            "approval_id": approval_id,
        }
        self.refunds.append(refund_record)
        return refund_record

    def update_ticket(self, ticket_id: str, status: str, notes: Optional[str] = None) -> Dict[str, Any]:
        self.audit_log.append({
            "action": "update_ticket",
            "ticket_id": ticket_id,
            "status": status,
            "notes": notes,
        })
        self.ticket["status"] = status
        if notes:
            self.ticket["notes"] = notes
        return {"ticket_id": ticket_id, "status": status}

    def get_final_state(self) -> Dict[str, Any]:
        """Provides full hidden ground truth snapshot for evaluators."""
        return {
            "environment_id": self.environment_id,
            "order": copy.deepcopy(self.order),
            "refunded_total_minor": self.order.get("refunded_amount_minor", 0),
            "refunds": copy.deepcopy(self.refunds),
            "approvals": copy.deepcopy(self.approvals),
            "ticket_status": self.ticket.get("status"),
            "audit_log": copy.deepcopy(self.audit_log),
        }
