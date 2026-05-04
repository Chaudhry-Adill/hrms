# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""ZKTeco / ESSL driver via the `pyzk` library.

ESSL biometric devices in India use the ZKTeco protocol family — a single
driver covers both. `pyzk` is an OPTIONAL dependency: when missing, the import
is gated and any attempt to use the driver raises BiometricSyncError with a
clear "install pyzk" message instead of crashing app loading.
"""

from __future__ import annotations

from hrms.hr.biometric.base import BiometricSyncError, Driver

try:
	from zk import ZK  # type: ignore[import-not-found]

	PYZK_AVAILABLE = True
except Exception:  # ImportError on missing pyzk; broad except for partial installs
	ZK = None  # type: ignore[assignment]
	PYZK_AVAILABLE = False


class ZKTecoDriver(Driver):
	def __init__(self, device):
		super().__init__(device)
		self.zk = None
		self.conn = None

	def _vendor_ctx(self) -> tuple[str, str]:
		return (
			getattr(self.device, "vendor", "ZKTeco"),
			getattr(self.device, "host", "?"),
		)

	def connect(self):
		if not PYZK_AVAILABLE:
			vendor, host = self._vendor_ctx()
			raise BiometricSyncError(
				"pyzk is not installed. Install it with `pip install pyzk` to use biometric devices.",
				vendor=vendor,
				host=host,
			)

		host = getattr(self.device, "host", None)
		port = int(getattr(self.device, "port", 4370) or 4370)
		password = getattr(self.device, "password", None)

		# Resolve password from password field if it's a Document property
		try:
			# Frappe Documents expose passwords via get_password
			if hasattr(self.device, "get_password"):
				try:
					password = self.device.get_password("password", raise_exception=False) or password
				except Exception:
					pass
		except Exception:
			pass

		try:
			self.zk = ZK(
				host,
				port=port,
				password=int(password) if password and str(password).isdigit() else 0,
				force_udp=False,
				ommit_ping=False,
				timeout=10,
			)
			self.conn = self.zk.connect()
		except Exception as e:
			vendor, hst = self._vendor_ctx()
			raise BiometricSyncError(f"connect failed: {e}", vendor=vendor, host=hst)

	def disconnect(self):
		try:
			if self.conn:
				self.conn.disconnect()
		except Exception:
			# Disconnect failures are non-fatal — swallow to avoid masking
			# the root cause from earlier in the run.
			pass
		finally:
			self.conn = None
			self.zk = None

	def fetch_logs(self, since_id: int | None = None) -> list[dict]:
		if not self.conn:
			vendor, host = self._vendor_ctx()
			raise BiometricSyncError("fetch_logs called before connect()", vendor=vendor, host=host)

		try:
			attendances = self.conn.get_attendance() or []
		except Exception as e:
			vendor, host = self._vendor_ctx()
			raise BiometricSyncError(f"get_attendance failed: {e}", vendor=vendor, host=host)

		out: list[dict] = []
		for a in attendances:
			# pyzk Attendance attrs: uid (record id), user_id, timestamp, status, punch
			log_id = getattr(a, "uid", None)
			if since_id is not None and log_id is not None:
				try:
					if int(log_id) <= int(since_id):
						continue
				except Exception:
					pass
			out.append(
				{
					"log_id": int(log_id) if log_id is not None else 0,
					"user_id": getattr(a, "user_id", None),
					"timestamp": getattr(a, "timestamp", None),
					"punch_type": getattr(a, "punch", None),
					"status": getattr(a, "status", None),
				}
			)
		return out

	def get_users(self) -> list[dict]:
		if not self.conn:
			vendor, host = self._vendor_ctx()
			raise BiometricSyncError("get_users called before connect()", vendor=vendor, host=host)

		try:
			users = self.conn.get_users() or []
		except Exception as e:
			vendor, host = self._vendor_ctx()
			raise BiometricSyncError(f"get_users failed: {e}", vendor=vendor, host=host)

		return [{"user_id": getattr(u, "user_id", None), "name": getattr(u, "name", None)} for u in users]
