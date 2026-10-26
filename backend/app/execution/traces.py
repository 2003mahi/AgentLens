from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models import TraceEvent

class TraceRecorder:
    def __init__(self, attempt_id: str, db: Optional[Session] = None):
        self.attempt_id = attempt_id
        self.db = db
        self.sequence_number = 0
        self.events: List[Dict[str, Any]] = []

    def record_event(
        self,
        event_type: str,
        duration_ms: Optional[float] = None,
        status: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.sequence_number += 1
        now_dt = datetime.now(timezone.utc)
        event_dict = {
            "attempt_id": self.attempt_id,
            "sequence_number": self.sequence_number,
            "event_type": event_type,
            "timestamp": now_dt,
            "duration_ms": duration_ms,
            "status": status,
            "payload": payload or {},
        }
        self.events.append(event_dict)

        if self.db:
            db_event = TraceEvent(
                attempt_id=self.attempt_id,
                sequence_number=self.sequence_number,
                event_type=event_type,
                timestamp=now_dt,
                duration_ms=duration_ms,
                status=status,
                payload=payload or {},
            )
            self.db.add(db_event)
            self.db.flush()

        return event_dict

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self.events)
