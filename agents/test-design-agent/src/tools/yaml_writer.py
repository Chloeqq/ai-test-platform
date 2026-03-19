from pathlib import Path
import yaml


def save_yaml(data: dict, output_path: str) -> str:

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    return str(path)