from dataclasses import dataclass
from datetime import datetime
import json
import logging
from pathlib import Path
from sys import stdout
from typing import Any, Self


@dataclass
class Progress:
    latest_complete_step: int = -1

    def __post_init__(self) -> None:
        nothing_dir = Path().cwd() / ".nothing"
        if nothing_dir.exists() and not nothing_dir.is_dir():
            message = f"{nothing_dir} exists but is not a directory."
            raise RuntimeError(message)
        elif not nothing_dir.exists():
            nothing_dir.mkdir()

        file_stem = nothing_dir / datetime.now().strftime("%Y%m%d-%H%M%S")

        self._logger = logging.getLogger(f"nothing-{file_stem.name}")
        self._logger.setLevel(logging.DEBUG)
        file = logging.FileHandler(
            filename=file_stem.with_suffix(".log"),
            mode="w",
        )
        file.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        file.setLevel(logging.DEBUG)
        self._logger.addHandler(file)
        # `console` allows a configurable level at which logging is also sent
        #  to STDOUT.
        console = logging.StreamHandler(stdout)
        console.setFormatter(
            logging.Formatter(
                "%(asctime)s %(message)s",
            )
        )
        console.setLevel(logging.INFO)
        self._logger.addHandler(console)

        self._file_path = file_stem.with_suffix(".json")

        self.save()

    @classmethod
    def load(cls, file_path: Path) -> Self:
        kwargs = json.loads(file_path.read_text())
        return cls(**kwargs)

    def save(self) -> None:
        state = self.__dict__.copy()
        _file_path = state.pop("_file_path", None)
        _logger = state.pop("_logger", None)
        if _file_path and _logger:
            json_rep = json.dumps(state, indent=0)
            Path(self._file_path).write_text(json_rep)
            self._logger.info(f"Progress saved to {self._file_path}")

    def __setattr__(self, key: Any, value: Any) -> None:
        super().__setattr__(key, value)
        self.save()
