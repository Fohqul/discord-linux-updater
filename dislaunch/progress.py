from threading import Thread
from time import sleep

import gi

gi.require_versions({"Adw": "1", "Gtk": "4.0"})
from gi.repository import Adw, Gtk


class ProgressWindow(Adw.Window):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.pulsing = True
		self.debounce = 0
		self.text = ""
		self.previous_progress = 0

		self.label = Gtk.Label()
		Thread(target=self._ellipsis_preloader).start()
		self.progress_bar = Gtk.ProgressBar()
		Thread(target=self._pulse).start()

		self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		self.box.append(self.label)
		self.box.append(self.progress_bar)

		self.set_default_size(1100, 600)
		self.set_resizable(False)
		self.set_content(self.box)

	def _pulse(self):
		while True:
			if self.pulsing:
				self.progress_bar.pulse()
				sleep(0.1)

	def _ellipsis_preloader(self):
		while True:
			for i in range(4):
				self.label.set_text(self.text + ("." * i))
				sleep(1)

	def use_activity_mode(self, use: bool):
		self.pulsing = use
		self.progress_bar.set_show_text(not use)

	def status(self, text, progress: float | None = None):
		self.text = text

		if self.pulsing or progress is None:
			return

		# self.progress_bar.set_fraction(progress)
		if self.debounce >= 2:
			self.progress_bar.set_fraction(progress)
			self.debounce = 0
		else:
			self.debounce += 1

		normalised = round(progress * 100)
		if self.previous_progress == normalised:
			return
		self.previous_progress = normalised
		self.progress_bar.set_text(str(normalised) + "%")


class ProgressManager:
	def __init__(self):
		self.app = Adw.Application()
