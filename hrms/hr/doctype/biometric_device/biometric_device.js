// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Biometric Device", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Test Connection"), () => {
			frappe.dom.freeze(__("Testing connection..."));
			frappe
				.call({
					method: "hrms.api.biometric.test_connection",
					args: { device: frm.doc.name },
				})
				.then((r) => {
					const res = r.message || {};
					frappe.msgprint({
						title: res.success ? __("Connection OK") : __("Connection Failed"),
						message: res.message || "",
						indicator: res.success ? "green" : "red",
					});
				})
				.always(() => frappe.dom.unfreeze());
		});

		frm.add_custom_button(__("Sync Now"), () => {
			frappe.confirm(__("Pull new attendance logs from this device now?"), () => {
				frappe.dom.freeze(__("Syncing device..."));
				frappe
					.call({
						method: "hrms.api.biometric.manual_sync",
						args: { device: frm.doc.name },
					})
					.then((r) => {
						const log_name = r.message;
						frappe.msgprint({
							title: __("Sync Started"),
							message: log_name
								? __("Sync log: <a href='/app/biometric-sync-log/{0}'>{0}</a>", [log_name])
								: __("Sync completed."),
							indicator: "blue",
						});
						frm.reload_doc();
					})
					.always(() => frappe.dom.unfreeze());
			});
		});

		frm.add_custom_button(__("Import Users"), () => {
			frappe.dom.freeze(__("Fetching users from device..."));
			frappe
				.call({
					method: "hrms.api.biometric.import_device_users",
					args: { device: frm.doc.name },
				})
				.then((r) => {
					const users = r.message || [];
					if (!users.length) {
						frappe.msgprint(__("No users found on device."));
						return;
					}
					const rows = users
						.map(
							(u) =>
								`<tr><td>${frappe.utils.escape_html(String(u.user_id))}</td>` +
								`<td>${frappe.utils.escape_html(String(u.name || ""))}</td></tr>`,
						)
						.join("");
					frappe.msgprint({
						title: __("Device Users ({0})", [users.length]),
						message: `<table class='table table-bordered'><thead><tr>
							<th>${__("Device User ID")}</th><th>${__("Name")}</th>
						</tr></thead><tbody>${rows}</tbody></table>`,
						wide: true,
					});
				})
				.always(() => frappe.dom.unfreeze());
		});
	},
});
