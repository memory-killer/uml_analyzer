"""
clang-uml sequence diagram JSON parser

Parser and data structures specialized for sequence diagrams.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Participant:
    """Participant in a sequence diagram (class, function, method, etc.)."""
    id: str
    name: str
    type: str  # class, function, method, etc.
    display_name: Optional[str] = None
    namespace: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        if self.namespace:
            return f"{self.namespace}::{self.name}"
        return self.name


@dataclass
class Message:
    """Message in a sequence diagram (function call, return, etc.)."""
    from_id: str
    to_id: str
    name: str
    type: str  # call, return, create, etc.
    message_scope: Optional[str] = None
    return_type: Optional[str] = None
    source_location: Optional[Dict[str, Any]] = None
    
    def __repr__(self) -> str:
        return f"{self.from_id} -> {self.to_id}: {self.name}"


@dataclass
class Activity:
    """Activity block (conditions, loops, etc.)."""
    type: str  # if, loop, alt, opt, etc.
    messages: List[Message] = field(default_factory=list)
    activities: List['Activity'] = field(default_factory=list)
    condition: Optional[str] = None


@dataclass
class SequenceDiagramData:
    """Container for all sequence diagram data."""
    name: str
    diagram_type: str
    participants: Dict[str, Participant]
    messages: List[Message]
    metadata: Dict[str, Any]
    start_from: Optional[str] = None  # starting function/method
    
    @property
    def participant_count(self) -> int:
        return len(self.participants)
    
    @property
    def message_count(self) -> int:
        return len(self.messages)
    
    def get_participant_by_name(self, name: str) -> Optional[Participant]:
        """Find participant by name."""
        for p in self.participants.values():
            if p.name == name or p.full_name == name:
                return p
        return None
    
    def get_calls_from(self, participant_id: str) -> List[Message]:
        """Get messages sent by a specific participant."""
        return [m for m in self.messages if m.from_id == participant_id]
    
    def get_calls_to(self, participant_id: str) -> List[Message]:
        """Get messages received by a specific participant."""
        return [m for m in self.messages if m.to_id == participant_id]


class SequenceDiagramParser:
    """Parser for clang-uml sequence diagram JSON."""
    
    def __init__(self):
        self.data: Optional[SequenceDiagramData] = None
    
    def parse_file(self, filepath: Path) -> SequenceDiagramData:
        """Parse a JSON file into sequence diagram data."""
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        return self.parse_dict(raw_data, filepath.stem)
    
    def parse_dict(self, raw_data: Dict[str, Any], name: str = "sequence") -> SequenceDiagramData:
        """Parse a raw dictionary into sequence diagram data."""
        # Parse participants
        participants = {}
        for p_data in raw_data.get("participants", []):
            p = self._parse_participant(p_data)
            participants[p.id] = p
        
        # Parse messages (recursively traverse activities and blocks)
        messages = []
        for seq_item in raw_data.get("sequences", []):
            messages.extend(self._extract_messages(seq_item))
        
        # Create the sequence diagram data object
        self.data = SequenceDiagramData(
            name=name,
            diagram_type=raw_data.get("diagram_type", "sequence"),
            participants=participants,
            messages=messages,
            metadata=raw_data.get("metadata", {}),
            start_from=raw_data.get("start_from")
        )
        
        return self.data
    
    def _parse_participant(self, p_data: Dict[str, Any]) -> Participant:
        """Parse a single participant."""
        return Participant(
            id=p_data.get("id", ""),
            name=p_data.get("name", ""),
            type=p_data.get("type", "class"),
            display_name=p_data.get("display_name"),
            namespace=p_data.get("namespace")
        )
    
    def _extract_messages(self, item: Dict[str, Any], messages: Optional[List[Message]] = None) -> List[Message]:
        """Recursively extract messages from an item."""
        if messages is None:
            messages = []
        
        # Direct message node
        if item.get("type") in ["call", "return"]:
            msg = Message(
                from_id=item.get("from", {}).get("id", ""),
                to_id=item.get("to", {}).get("id", ""),
                name=item.get("name", ""),
                type=item.get("type", "call"),
                message_scope=item.get("scope"),
                return_type=item.get("return_type"),
                source_location=item.get("source_location")
            )
            messages.append(msg)
        
        # Traverse nested activity blocks
        if "messages" in item:
            for sub_item in item["messages"]:
                self._extract_messages(sub_item, messages)
        
        # Condition/loop and other blocks
        for key in ["if_blocks", "else_blocks", "case_blocks", "loop_blocks"]:
            if key in item:
                for block in item[key]:
                    self._extract_messages(block, messages)
        
        return messages
    
    def get_statistics(self) -> Dict[str, Any]:
        """Return statistics for the parsed sequence diagram."""
        if not self.data:
            return {}
        
        return {
            "diagram_name": self.data.name,
            "diagram_type": self.data.diagram_type,
            "total_participants": self.data.participant_count,
            "total_messages": self.data.message_count,
            "start_from": self.data.start_from,
            "clang_uml_version": self.data.metadata.get("clang_uml_version"),
            "llvm_version": self.data.metadata.get("llvm_version"),
        }


class SequenceDiagramGenerator:
    """PlantUML generator for sequence diagrams."""
    
    def __init__(self, diagram_data: SequenceDiagramData):
        self.data = diagram_data
    
    def generate_puml(
        self,
        participant_filter: Optional[set] = None,
        title: Optional[str] = None,
        max_depth: Optional[int] = None
    ) -> str:
        """
        Generate PlantUML sequence diagram code.
        
        Args:
            participant_filter: Set of participant IDs to include (all if None).
            title: Diagram title.
            max_depth: Maximum call depth (currently unused).
        """
        lines = ["@startuml"]
        
        if title:
            lines.append(f"title {title}")
        
        lines.append("")
        
        # Declare participants
        participants = self.data.participants
        if participant_filter:
            participants = {k: v for k, v in participants.items() if k in participant_filter}
        
        for p in participants.values():
            p_type = "participant" if p.type == "class" else "participant"
            lines.append(f'{p_type} "{p.display_name or p.name}" as {self._get_alias(p.id)}')
        
        lines.append("")
        
        # Messages
        for msg in self.data.messages:
            # Filter messages if needed
            if participant_filter and (msg.from_id not in participant_filter or msg.to_id not in participant_filter):
                continue
            
            from_alias = self._get_alias(msg.from_id)
            to_alias = self._get_alias(msg.to_id)
            
            if msg.type == "return":
                lines.append(f"{to_alias} --> {from_alias}: {msg.name}")
            else:
                lines.append(f"{from_alias} -> {to_alias}: {msg.name}")
        
        lines.append("")
        lines.append("'Generated by uml_processor")
        lines.append("@enduml")
        
        return "\n".join(lines)
    
    def _get_alias(self, participant_id: str) -> str:
        """Convert participant ID into a PlantUML alias."""
        return f"P_{participant_id[:16]}"
    
    def save_puml(self, output_path: Path, **kwargs):
        """Save generated PlantUML to a file."""
        puml_content = self.generate_puml(**kwargs)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(puml_content, encoding='utf-8')


if __name__ == "__main__":
    # Simple manual test
    parser = SequenceDiagramParser()
    
    # Test with sample data
    sample = {
        "diagram_type": "sequence",
        "name": "test_sequence",
        "participants": [
            {"id": "1", "name": "main", "type": "function"},
            {"id": "2", "name": "UserService", "type": "class", "namespace": "app"},
        ],
        "sequences": [
            {
                "type": "call",
                "from": {"id": "1"},
                "to": {"id": "2"},
                "name": "createUser",
            }
        ],
        "metadata": {}
    }
    
    data = parser.parse_dict(sample)
    print(f"✅ Participants: {data.participant_count}, Messages: {data.message_count}")
    
    gen = SequenceDiagramGenerator(data)
    print("\nGenerated PlantUML:")
    print(gen.generate_puml())

