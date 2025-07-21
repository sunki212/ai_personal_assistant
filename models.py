from dataclasses import dataclass
import json


@dataclass
class UserData:
    user_id: int
    username: str
    default_communication: str = ""

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)