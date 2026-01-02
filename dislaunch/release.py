import tarfile

import gi

gi.require_version("Adw", "1")
from datetime import datetime
from json import loads
from pathlib import Path
from shutil import rmtree
from subprocess import run
from threading import Thread
from typing import Callable

from const import (
	BD_PATHS,
	CACHE_HOME,
	CONFIG_HOME,
	DATA_HOME,
	ID,
	RELEASE_DATA_PATHS,
	RELEASES,
	BetterDiscordRelease,
	Release,
)
from gi.repository import Adw, GLib
from progress import ProgressWindow
from pydantic import BaseModel
from requests import get


def _download(
	url: str,
	output: Path | None = None,
	progress: Callable[[float], None] | None = None,
):
	response = get(url, stream=(output is not None))
	if response.status_code != 200:
		raise Exception("Request failed: " + str(response.status_code))
	total_size = int(response.headers.get("content-length", 0))
	downloaded_size = 0

	if output is not None:
		with output.open("wb") as f:
			for chunk in response.iter_content(chunk_size=2048 * 100):
				f.write(chunk)
				downloaded_size += len(chunk)
				if progress:
					progress(
						downloaded_size / total_size
					)  # todo smoother progress bar (will need refactoring)

	return response


class _DiscordUpdate(BaseModel):
	name: str
	pub_date: datetime


class _ReleaseModel(BaseModel):
	version: str = ""
	last_checked: float = 0.0
	bd: BetterDiscordRelease = ""


def _get_release(release: Release) -> _ReleaseModel:
	release_path = RELEASE_DATA_PATHS[release]

	if not release_path.exists():
		_set_release(release, _ReleaseModel())
		return _ReleaseModel()

	with release_path.open("r", encoding="utf-8") as f:
		content = f.read()
		if content == "":
			_set_release(release, _ReleaseModel())
			return _ReleaseModel()
		return _ReleaseModel(**loads(content))


def _set_release(release: Release, model: _ReleaseModel):
	with RELEASE_DATA_PATHS[release].open("w", encoding="utf-8") as release_data:
		release_data.write(model.model_dump_json(indent=4))


def _get_latest_bd(canary: bool):
	return get(
		"https://api.github.com/repos/BetterDiscord/BetterDiscord/releases"
	).json()[0 if canary else 1]


def _install_bd(canary: bool):
	_download(
		_get_latest_bd(canary)["assets"][0]["browser_download_url"], BD_PATHS[canary]
	)


def _get_bd(canary: bool):
	bd_path = BD_PATHS[canary]

	if not bd_path.exists():
		get("https://api.github.com/repos/BetterDiscord/BetterDiscord/releases").json()
		_download

	return bd_path


def _clean_bd(canary: bool):
	for release in ["stable", "ptb", "canary"]:
		release_data = _get_release(release)
		if release_data.bd == "canary" if canary else "stable":
			return

	BD_PATHS[canary].unlink(missing_ok=True)


class _ReleaseManager:
	def __init__(self, release: Release):
		self.release = release
		self.progress_window = ProgressWindow()

	def get_normalised(self):
		release = self.release
		if release == "stable":
			return "Discord Stable"
		elif release == "ptb":
			return "Discord PTB"
		elif release == "canary":
			return "Discord Canary"
		else:
			raise ValueError("Invalid release: " + str(release))

	def set_app(self, app: Adw.Application):
		self.progress_window.set_application(app)

	def get_data(self) -> _ReleaseModel:
		return _get_release(self.release)

	def _set_property(self, key: str, value):
		data = _get_release(self.release)
		setattr(data, key, value)
		_set_release(self.release, data)

	def get_version(self) -> str:
		return self.get_data().version

	def _set_version(self, version: str):
		self._set_property("version", version)

	def get_last_checked(self) -> float:
		return datetime.fromtimestamp(self.get_data().last_checked)

	def get_bd(self) -> BetterDiscordRelease:
		return self.get_data().bd

	def _set_bd(self, bd: BetterDiscordRelease):
		self._set_property("bd", bd)

	def _set_status(self, status: str, progress: float | None = None):
		self.progress_window.status(status, progress)

	def _set_use_activity_mode(self, use: bool):
		self.progress_window.use_activity_mode(use)

	def _set_index_js(self, content):
		index_js_path = (
			CONFIG_HOME
			/ ("discord" + self.release if self.release != "stable" else "")
			/ self.get_version()
			/ "modules"
			/ "discord_desktop_core"
			/ "index.js"
		)
		with index_js_path.open("w", encoding="utf-8") as index_js:
			index_js.write(content)

	def get_install(self) -> Path:
		return DATA_HOME / self.release

	def get_install_lockfile(self) -> Path:
		return Path(f"/tmp/dislaunch-install-{self.release}.lock")

	def get_latest_update(self) -> _DiscordUpdate:
		return _DiscordUpdate(
			**_download(
				f"https://discord.com/api/{self.release}/updates?platform=linux"
			).json()
		)

	def update_available(self, update: _DiscordUpdate | None = None) -> bool:
		update = update or self.get_latest_update()
		version = self.get_version()
		last_checked = self.get_last_checked()
		if version == "":
			return True
		self._set_property("last_checked", datetime.now().timestamp())

		if update.name == version or last_checked == 0.0:
			return False
		return True

	def install(self, callback):
		lockfile = self.get_install_lockfile()
		if lockfile.exists():
			return
		update = self.get_latest_update()
		if not self.update_available(update):
			return
		lockfile.touch()

		self.progress_window.present()
		output = CACHE_HOME / (self.release + ".tar.gz")

		def indicate_progress(progress: float):
			self._set_use_activity_mode(False)
			self._set_status(
				f"Downloading {self.get_normalised()} {update.name}", progress
			)

		_download(
			f"https://discord.com/api/download/{self.release}?platform=linux&format=tar.gz",
			output,
			indicate_progress,
		)

		with tarfile.open(output, "r:gz") as tarball:
			install_path = self.get_install()
			self._set_use_activity_mode(True)
			self._set_status(f"Installing to {install_path}")
			tarball.extractall(path=install_path)

		self._set_version(update.name)

		if self.get_bd() != "":
			self._set_status("Injecting BetterDiscord")
			self.inject_bd()

		self.progress_window.hide()
		self.get_install_lockfile().unlink(missing_ok=True)
		callback()

	def uninstall(self):
		install = self.get_install()
		if install.exists() and install.is_dir():
			rmtree(install)
		self._set_version("")
		RELEASE_DATA_PATHS[self.release].unlink(missing_ok=True)

	def inject_bd(self):
		canary = self.get_bd() == "canary"
		self._set_bd("canary" if canary else "stable")
		self._set_index_js(
			f"require('{str(_get_bd(canary))}');\nmodule.exports = require('./core.asar');"
		)

	def uninject_bd(self):
		bd = self.get_bd()
		if bd == "":
			return
		self._set_bd("")
		self._set_index_js("module.exports = require('./core.asar');")
		_clean_bd(bd == "canary")

	def _create_progress_window(self):
		return  # this was seemingly never implemented properly or fully
		progress_window = ProgressWindow()

		def activate(app: Adw.Application):
			progress_window.set_application(app)
			progress_window.present()

		app = Adw.Application(application_id=ID + ".Updater")
		app.connect("activate", activate)
		app.run()

		return progress_window, app

	def launch(self, *args):
		return  # this was seemingly never implemented properly or fully
		if self.update_available():
			self.install(self._create_progress_window())

		if self.get_bd() != "":
			self.inject_bd()

		executable = self.get_install()
		if self.release == "stable":
			executable /= "Discord" / "Discord"
		elif self.release == "ptb":
			executable /= "DiscordPTB" / "DiscordPTB"
		elif self.release == "canary":
			executable /= "DiscordCanary" / "DiscordCanary"
		run([executable, *args], check=True)


managers = {release: _ReleaseManager(release) for release in RELEASES}
