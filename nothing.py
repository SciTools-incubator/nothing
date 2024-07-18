#!/usr/bin/env python3
"""Functionality to support do-nothing workflows.

https://blog.danslimmon.com/2019/07/15/do-nothing-scripting-the-key-to-gradual-automation/
"""

import abc
from argparse import ArgumentParser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from pathlib import Path
from sys import stderr, stdout
from time import sleep
from typing import Any, Optional, Self


@dataclass
class Progress(abc.ABC):
    """The base class for do-nothing workflows.

    Includes functionality for saving and loading progress. Intended entry
    point is :meth:`main`, which provides a command-line interface. Ensure
    all variables that track progress are included as attributes, and are
    serialisable to JSON; attributes beginning with `_` are excluded from the
    save/load functionality.
    """

    latest_complete_step: int = -1
    """:meth:`run` will begin at this step + 1. Enables resuming from a saved state."""

    _dry_run: bool = False
    """If True, will only attempt instantiation, without saving or running get_steps."""

    def __new__(cls, *args: Any, **kwargs: Any) -> "Progress":
        # It is essential to correct operation that cls itself is @dataclass
        #  decorated, not just inheriting decoration from a parent class.
        #  (Otherwise cls attributes will not be included in cls.__init__).
        cls = dataclass(cls)
        return super().__new__(cls)

    def __setattr__(self, key: Any, value: Any) -> None:
        # Call :meth:`save` whenever an attribute is set.
        super().__setattr__(key, value)
        if not self._dry_run and self.ready:
            self.save()

    def __post_init__(self) -> None:
        """Set up logging and save-file, then call :meth:`run`."""
        if self._dry_run:
            return

        file_stem = self._get_file_stem()
        self._logger = self._get_logger(file_stem)
        self._file_path = file_stem.with_suffix(".json")
        self._logger.info(f"Progress will be saved to: {self._file_path}")

        self.save()
        self.run()

    @staticmethod
    def _get_logger(file_stem: Path) -> logging.Logger:
        """Create a logger for informing the user and recording activity."""
        logger = logging.getLogger(f"nothing-{file_stem.name}")
        logger.setLevel(logging.DEBUG)
        file = logging.FileHandler(
            filename=file_stem.with_suffix(".log"),
            mode="w",
        )
        file.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        file.setLevel(logging.DEBUG)
        logger.addHandler(file)
        # `console` allows a configurable level at which logging is also sent to STDOUT.
        console = logging.StreamHandler(stdout)
        console.setFormatter(
            logging.Formatter(
                "%(asctime)s %(message)s",
            )
        )
        console.setLevel(logging.INFO)
        logger.addHandler(console)

        return logger

    @classmethod
    def _get_file_stem(cls) -> Path:
        """Create a date-stamped path for storing progress and logs.

        Creates the parent directory if necessary.
        """
        nothing_dir = Path().cwd() / ".nothing"
        if nothing_dir.exists() and not nothing_dir.is_dir():
            message = f"{nothing_dir} exists but is not a directory."
            raise RuntimeError(message)
        elif not nothing_dir.exists():
            nothing_dir.mkdir()

        date_time_string = datetime.now().strftime("%Y%m%d-%H%M%S")
        return nothing_dir / f"{cls.__name__}_{date_time_string}"

    @classmethod
    def load(cls, file_path: Path, dry_run: bool = False) -> Self:
        """Instantiate by loading a previous state from a saved file."""
        kwargs = json.loads(file_path.read_text())
        del kwargs["comments"]
        return cls(_dry_run=dry_run, **kwargs)

    @classmethod
    def main(cls) -> None:
        """Command-line interface for the do-nothing workflow."""
        parser = ArgumentParser(
            description=cls.get_cmd_description(),
        )
        subparsers = parser.add_subparsers(required=True)

        helps = {
            "new": "Start the workflow fresh from step 0.",
            "load": (
                "Resume a previous workflow by loading its saved JSON progress file. "
                "NOTE this file can be manually edited to start at an alternative step "
                "or use alternative values."
            ),
            "template": (
                "Create a new JSON progress file, which can be loaded by the `load` "
                "subcommand. The file is populated with the default values; intended "
                "for manual editing."
            ),
        }

        new, load, template = [
            subparsers.add_parser(name=name, help=helps[name], description=helps[name])
            for name in helps
        ]

        load.add_argument(
            "file_path",
            type=Path,
            help="The path of the JSON progress file to be loaded.",
        )

        def create_template_file() -> None:
            instance = cls(_dry_run=True)
            instance._logger = logging.getLogger("nothing")
            instance._file_path = cls._get_file_stem().with_name(
                f"{cls.__name__}_template.json"
            )
            instance.save()
            print(f"Template saved to: {instance._file_path}")

        new.set_defaults(func=lambda _: cls())
        load.set_defaults(func=lambda p: cls.load(p.file_path))
        template.set_defaults(func=lambda _: create_template_file())

        parsed = parser.parse_args()
        parsed.func(parsed)

    @property
    def ready(self) -> bool:
        """Return True once the essential attributes have been set."""
        return all(
            [
                k in self.__dict__
                for k in (
                    "_logger",
                    "_file_path",
                )
            ]
        )

    @property
    def state(self) -> dict[str, Any]:
        """Current values of all non-private dataclass attributes.

        Intended that these are the values that are used through the do-nothing
        workflow and track its progress. They are the values that are required
        for recreating the instance e.g. via :meth:`load`.
        """
        return {
            k: self.__dict__[k] for k in self.__match_args__ if not k.startswith("_")
        }

    @property
    def _save_file_comments(self) -> list[list[str]]:
        """Comments that will be stored, but not loaded, in the save file.

        Each comment is ``list[str]`` as a JSON-compatible way to store
        multiline strings.
        """
        comments: list[list[str]] = []
        cls_name = self.__class__.__name__
        comments.append(
            [
                f"This file stores the progress of the {cls_name} do-nothing workflow.",
                "It can be loaded to resume progress, and edited to resume from",
                "an alternative step or use alternative values.",
            ]
        )
        comments.append(
            [
                "Step names:",
                *[f"{ix}: {step.__name__}" for ix, step in enumerate(self.get_steps())],
            ]
        )
        return comments

    def run(self) -> None:
        """Iteratively run the functions in :meth:`get_steps`.

        Begins at :attr:`latest_complete_step` + 1, which enables started from
        previously saved progress via :meth:`load`.
        """

        index_first = self.latest_complete_step + 1
        for step in self.get_steps()[index_first:]:
            index_current = self.latest_complete_step + 1
            self.print("")
            self._logger.info(f"*** STEP {index_current} STARTING ***")
            step(self=self)
            self._logger.info(f"*** STEP {index_current} COMPLETE ***")
            self.latest_complete_step = index_current
        self._logger.info("*** WORKFLOW COMPLETE ***")

    def save(self) -> None:
        """Save :attr:`state` to a JSON file, enabling later reloading.

        Includes validation that the saved file can be successfully reloaded.
        """
        self._logger.debug(f"Saving state: {self.state}")
        save_dict = dict(comments=self._save_file_comments) | self.state
        json_rep = json.dumps(save_dict, indent=2)
        Path(self._file_path).write_text(json_rep)
        self._logger.debug("Save complete.")

        try:
            _ = self.__class__.load(self._file_path, dry_run=True)
        except Exception as exception:
            message = (
                f"{self.__class__.__name__} instance saves to an "
                f"unloadable file - exception below:\n\n{exception}"
            )
            self._logger.error(message)
            raise ValueError(message)

    @classmethod
    @abc.abstractmethod
    def get_cmd_description(cls) -> str:
        """Return a string describing the command-line interface."""
        return "SciTools do-nothing workflow"

    @classmethod
    @abc.abstractmethod
    def get_steps(cls) -> list[Callable[..., None]]:
        """Return a list of functions that represent the steps of the process."""
        return NotImplemented

    @staticmethod
    def print(message: str) -> None:
        """Print a line break, then a message, then wait 1sec."""
        print()
        print(message)
        # Help with flow/visibility by waiting 1secs before proceeding.
        sleep(1)

    @staticmethod
    def get_input(message: str, expected_inputs: str) -> str:
        """Call :func:`input` with a custom message and input hint."""
        Progress.print(message)
        return input(expected_inputs + " : ")

    @staticmethod
    def wait_for_done(message: str) -> None:
        """Print a message, then wait for user confirmation to proceed."""
        Progress.print(message)
        done = False
        while not done:
            done = input("Step complete? y / [n] : ").casefold() == "y".casefold()

    @staticmethod
    def report_problem(message: str) -> None:
        """Print a message to STDERR, then wait 0.5secs."""
        print(message, file=stderr)
        # To ensure correct sequencing of messages.
        sleep(0.5)

    def set_value_from_input(
        self,
        key: str,
        message: str,
        expected_inputs: str,
        post_process: Optional[Callable[[str], Any]],
    ) -> None:
        """Set an attribute value using :meth:`get_input`, defaulting to any current value.

        The current value is typically present if instantiated via
        :meth:`load`.

        Parameters
        ----------
        key : str
            The attribute to set.
        message : str
            The message shown before user input (see :meth:`get_input`).
        expected_inputs : str
            Hint shown before user input (see :meth:`get_input`).
        post_process : callable, optional
            Function defining anything to be done to the input before setting.
            Must take a string as the only input, and return the desired value
            to be set. If the function returns ``None`` (e.g. if input fails
            validation) then input will be requested from the user again.

        """
        # Just keep the existing value if no post_process is provided.
        post_process = post_process or (lambda x: x)

        default = getattr(self, key, None)
        input_final = None
        while input_final is None:
            if default is not None:
                expected_inputs_final = (
                    f"{expected_inputs}\nOR input nothing for `{default}`"
                )
            else:
                expected_inputs_final = expected_inputs
            input_new = Progress.get_input(message, expected_inputs_final)
            if input_new == "":
                input_final = default
            else:
                input_final = post_process(input_new)

        self.__setattr__(key, input_final)


class Demo(Progress):
    var_1: int = 0
    var_2: str | None = None

    @classmethod
    def get_cmd_description(cls) -> str:
        return "Demo workflow for nothing.py"

    def set_var_1(self) -> None:
        self.var_1 = datetime.now().day

    def set_var_2(self) -> None:
        self.set_value_from_input(
            key="var_2",
            message="Input a string",
            expected_inputs="Either A or B or C",
            post_process=lambda x: x if x in ["A", "B", "C"] else None,
        )

    @classmethod
    def get_steps(cls) -> list[Callable[..., None]]:
        return [
            cls.set_var_1,
            cls.set_var_2,
        ]


if __name__ == "__main__":
    Progress.main()
