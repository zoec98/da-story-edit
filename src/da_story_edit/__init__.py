import sys

from da_story_edit.config import ConfigError, load_and_validate_config


def main() -> None:
    try:
        load_and_validate_config()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc

    print("Configuration looks good. Next: implement gallery processing pipeline.")
