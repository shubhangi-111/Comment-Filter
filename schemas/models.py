from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

@dataclass
class ModerationPrediction:
    comment: str
    is_toxic: bool
    label: str
    category: str
    confidence: float
    threat_detected: bool
    author_username: str = "Anonymous"
    author_name: str = "Anonymous User"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ModerationLogDTO:
    id: Optional[int]
    user_id: Optional[str]
    author_username: str
    author_name: str
    comment_text: str
    is_toxic: bool
    label: str
    category: str
    confidence: float
    threat_detected: bool
    platform: str
    created_at: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
