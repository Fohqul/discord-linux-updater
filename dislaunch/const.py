from os import environ
from pathlib import Path
from typing import Literal

ID = "io.github.Fohqul.Dislaunch"

HOME = Path(environ.get("HOME", "~"))
DATA_HOME = Path(environ.get("XDG_DATA_HOME", HOME / ".local" / "share")) / ID
DATA_HOME.mkdir(exist_ok=True)
CONFIG_HOME = Path(environ.get("XDG_CONFIG_HOME", HOME / ".local")) / ID
CONFIG_HOME.mkdir(exist_ok=True)
CACHE_HOME = Path(environ.get("XDG_CACHE_HOME", HOME / ".cache")) / ID
CACHE_HOME.mkdir(exist_ok=True)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

type Release = Literal["stable", "ptb", "canary"]
RELEASES: list[Release] = ["stable", "ptb", "canary"]
type BetterDiscordRelease = Literal["", "stable", "canary"]

RELEASE_DATA_PATHS: dict[Release, Path] = {
	release: DATA_HOME / f"{release}.json" for release in RELEASES
}
BD_PATHS = {
	True: DATA_HOME / "bd-canary.asar",
	False: DATA_HOME / "bd-stable.asar",
}
