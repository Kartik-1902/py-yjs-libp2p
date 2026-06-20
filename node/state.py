from dataclasses import dataclass, asdict


class SharedDocument:
    def __init__(
        self,
        content: str = "",
        version: int = 0,
        last_mod_by: str = "",
        last_updated_at: float = 0.0,
    ):
        self.content = content
        self.version = version
        self.last_mod_by = last_mod_by
        self.last_updated_at = last_updated_at

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "version": self.version,
            "last_mod_by": self.last_mod_by,
            "last_updated_at": self.last_updated_at,
        }


@dataclass
class DocumentUpdate:
    content: str
    version: int
    last_mod_by: str
    last_updated_at: float

    def serialize(self) -> bytes:
        import json

        return json.dumps(asdict(self)).encode("utf-8")

    @classmethod
    def deserialize(cls, data: bytes) -> "DocumentUpdate":
        import json

        return cls(**json.loads(data.decode("utf-8")))
