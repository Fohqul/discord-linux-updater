from sys import argv
from threading import Thread

import gi
from const import DATE_FORMAT, ID, Release
from progress import ProgressWindow
from release import managers

gi.require_versions({"Adw": "1", "Gtk": "4.0"})
from gi.repository import Adw, Gtk


class ReleaseGroup(Adw.PreferencesGroup):
	def __init__(self, app: Adw.Application, release: Release, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.release = release
		self.manager = managers[release]
		self.manager.set_app(app)

		self.not_installed = Gtk.Label()
		self.not_installed.set_markup("<i>Not installed</i>")
		self.install_button = Gtk.Button(
			label=f"Install {self.manager.get_normalised()}"
		)
		self.install_button.connect("clicked", self.install_button_clicked)

		self.update_button = Gtk.Button()
		self.update_button.connect("clicked", self.update_button_clicked)
		self.uninstall_button = Gtk.Button(label="Uninstall")
		self.uninstall_button.connect("clicked", self.uninstall_button_clicked)
		self.update_row = Adw.ActionRow()
		self.update_row.add_prefix(self.not_installed)
		self.update_row.add_suffix(self.install_button)
		self.update_row.add_suffix(self.update_button)
		self.update_row.add_suffix(self.uninstall_button)

		self.bd_apply = Gtk.Button(label="Apply")
		self.bd_apply.connect("clicked", self.bd_apply_clicked)
		self.bd_drop_down = Gtk.DropDown.new_from_strings(
			["Disabled", "Stable", "Canary"]
		)
		self.bd_row = Adw.ActionRow(title="BetterDiscord")
		self.bd_row.set_visible(False)
		self.bd_row.add_suffix(self.bd_apply)
		self.bd_row.add_suffix(self.bd_drop_down)

		self.add(self.update_row)
		self.add(self.bd_row)

		self.when_installed = {
			self.not_installed: False,
			self.install_button: False,
			self.uninstall_button: True,
			self.update_button: True,
			self.bd_row: True,
		}
		self.refresh()

	def refresh(self):
		version = self.manager.get_version()
		installed = version != ""
		self.update_available = installed and self.manager.update_available()
		is_installing = self.manager.get_install_lockfile().exists()

		self.set_title(
			self.manager.get_normalised()
			+ (" (update available!)" if self.update_available else "")
		)

		self.update_row.set_title(f"Installed version: {version}" if installed else "")
		self.update_row.set_subtitle(
			("Last checked: " + self.manager.get_last_checked().strftime(DATE_FORMAT))
			if installed
			else ""
		)

		self.install_button.set_label("Installing..." if is_installing else "Install")
		self.install_button.set_sensitive(not is_installing)
		self.uninstall_button.set_label("Uninstall")
		self.uninstall_button.set_sensitive(True)
		self.update_button.set_label(
			"Update"
			if self.update_available
			else "Updating..."
			if is_installing
			else "Check for updates"
		)
		self.update_button.set_sensitive(not is_installing)
		self.bd_apply.set_label("Apply")
		self.bd_apply.set_sensitive(True)

		for widget, show_when_installed in self.when_installed.items():
			widget.set_visible(installed == show_when_installed)

		self.bd_drop_down.set_selected(
			["", "stable", "canary"].index(self.manager.get_bd())
		)

	def install_button_clicked(self, _):
		self.install_button.set_sensitive(False)
		self.install_button.set_label("Installing...")
		Thread(target=self.manager.install, args=(self.refresh,)).start()

	def uninstall_button_clicked(self, _):
		self.uninstall_button.set_sensitive(False)
		self.uninstall_button.set_label("Uninstalling...")
		self.manager.uninstall()
		self.refresh()

	def set_update_available(self):
		self.update_available = self.manager.update_available()

	def update_button_clicked(self, _):
		self.update_button.set_sensitive(False)
		if self.update_available:
			self.update_button.set_label("Updating...")
			Thread(target=self.manager.install, args=(self.refresh,)).start()
		else:
			self.update_button.set_label("Checking...")
			self.set_update_available()
		self.refresh()

	def bd_apply_clicked(self):
		self.bd_apply.set_sensitive(False)
		self.bd_apply.set_label("Applying...")

		selected = self.bd_drop_down.get_selected_item().get_string()
		if selected == "Disabled":
			self.manager.uninject_bd()
		else:
			self.manager.inject_bd(selected == "Canary")


def activate(app):
	print("gui")
	box = Gtk.Box()
	box.set_orientation(Gtk.Orientation.VERTICAL)
	box.append(ReleaseGroup(app, "stable"))
	box.append(ReleaseGroup(app, "ptb"))
	box.append(ReleaseGroup(app, "canary"))

	app_window = Gtk.ApplicationWindow(application=app)
	app_window.set_child(box)
	app_window.set_default_size(700, 900)
	app_window.set_resizable(False)
	app_window.set_title("Dislaunch")
	app_window.set_titlebar(Adw.HeaderBar())
	app_window.present()


def main():
	app = Adw.Application(application_id=ID)
	app.connect("activate", activate)
	app.run(argv)


if __name__ == "__main__":
	main()
