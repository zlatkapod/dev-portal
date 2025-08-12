import os


def load_env_from_dotenv(dotenv_path: str = ".env") -> None:
    """
    Minimal .env loader (no external packages).
    Supports lines like: KEY=value or KEY="value with spaces".
    Existing environment variables are not overridden.
    """
    if not os.path.isfile(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        # Silent fail to not break the app if .env parsing fails
        pass
