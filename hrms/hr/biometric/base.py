# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Abstract biometric driver interface.

Each concrete driver (e.g. ZKTecoDriver) extends Driver and implements
connect / disconnect / fetch_logs / get_users.

The Biometric Device controller picks a driver based on `device.vendor` and
calls these methods. Drivers MUST raise BiometricSyncError on protocol failures
so the controller can record them in Biometric Sync Log without crashing the
scheduler.
"""

from __future__ import annotations


class BiometricSyncError(Exception):
	"""Raised by drivers when a connection or fetch operation fails."""

	def __init__(self, message: str, vendor: str | None = None, host: str | None = None):
		self.vendor = vendor
		self.host = host
		ctx = ""
		if vendor or host:
			ctx = f" [{vendor or '?'}@{host or '?'}]"
		super().__init__(f"{message}{ctx}")


class Driver:
	"""Abstract base. Subclasses implement vendor protocol details."""

	def __init__(self, device):
		# device is a Biometric Device document. Avoid importing the controller
		# here to keep the abstract layer free of Frappe dependencies — the
		# instance is duck-typed (host, port, password, vendor, device_name).
		self.device = device

	def connect(self):
		raise NotImplementedError

	def disconnect(self):
		raise NotImplementedError

	def fetch_logs(self, since_id: int | None = None) -> list[dict]:
		"""Return a list of dicts: {user_id, timestamp, punch_type, log_id?}.

		`since_id` is an opaque cursor stored on the device — drivers that don't
		support server-side filtering should filter client-side.
		"""
		raise NotImplementedError

	def get_users(self) -> list[dict]:
		"""Return a list of dicts: {user_id, name}."""
		raise NotImplementedError
