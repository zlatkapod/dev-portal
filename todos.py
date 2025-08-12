import os
from typing import List

TODOS_FILE = os.path.join(os.path.dirname(__file__), "data", "todos.csv")

def _ensure_todos_file():
    os.makedirs(os.path.dirname(TODOS_FILE), exist_ok=True)
    if not os.path.exists(TODOS_FILE):
        with open(TODOS_FILE, "w", encoding="utf-8") as f:
            f.write("")

def read_todos() -> List[str]:
    _ensure_todos_file()
    items: List[str] = []
    try:
        with open(TODOS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                text = line.rstrip("\n\r")
                if text:
                    items.append(text)
    except Exception:
        # On any read error, treat as empty
        items = []
    return items

def write_todos(lines: List[str]) -> None:
    _ensure_todos_file()
    with open(TODOS_FILE, "w", encoding="utf-8") as f:
        for line in lines:
            if line:
                f.write(line.replace("\n", " ").strip() + "\n")