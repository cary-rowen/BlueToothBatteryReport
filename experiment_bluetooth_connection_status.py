"""Experimental Bluetooth battery/connection probe for Windows.

This script does not modify the NVDA add-on. It reuses the current
PnP-based battery probe and prints extra connection-related signals so we
can judge whether disconnected devices can be filtered reliably.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

import validate_bluetooth_battery as base


DEVPROP_TYPE_UINT32 = 0x00000007
DEVPROP_TYPE_BOOLEAN = 0x00000011
CR_BUFFER_SMALL = 26

DN_DRIVER_LOADED = 0x00000002
DN_STARTED = 0x00000008
DN_DISABLEABLE = 0x00002000
DN_REMOVABLE = 0x00004000
DN_NT_ENUMERATOR = 0x00800000
DN_NT_DRIVER = 0x01000000
DN_DEVICE_DISCONNECTED = 0x02000000


DEVPKEY_DEVICE_CONTAINER_IS_CONNECTED = base.DEVPROPKEY(
	base.GUID(
		0x78C34FC8,
		0x104A,
		0x4ACA,
		(ctypes.c_ubyte * 8)(0x9E, 0xA4, 0x52, 0x4D, 0x52, 0x99, 0x6E, 0x57),
	),
	55,
)

DEVPKEY_DEVICE_DEVNODE_STATUS = base.DEVPROPKEY(
	base.GUID(
		0x4340A6C5,
		0x93FA,
		0x4706,
		(ctypes.c_ubyte * 8)(0x97, 0x2C, 0x7B, 0x64, 0x80, 0x08, 0xA5, 0xA7),
	),
	2,
)

PKEY_DEVICES_AEP_IS_CONNECTED = base.DEVPROPKEY(
	base.GUID(
		0xA35996AB,
		0x11CF,
		0x4935,
		(ctypes.c_ubyte * 8)(0x8B, 0x61, 0xA6, 0x76, 0x10, 0x81, 0xEC, 0xDF),
	),
	7,
)


SetupDiGetDevicePropertyW = base.setupapi.SetupDiGetDevicePropertyW
SetupDiGetDevicePropertyW.argtypes = [
	ctypes.c_void_p,
	ctypes.POINTER(base.SP_DEVINFO_DATA),
	ctypes.POINTER(base.DEVPROPKEY),
	ctypes.POINTER(wintypes.ULONG),
	ctypes.POINTER(ctypes.c_byte),
	wintypes.DWORD,
	ctypes.POINTER(wintypes.DWORD),
	wintypes.DWORD,
]
SetupDiGetDevicePropertyW.restype = wintypes.BOOL


bthprops = ctypes.WinDLL("bthprops.cpl", use_last_error=True)


class SYSTEMTIME(ctypes.Structure):
	_fields_ = [
		("wYear", wintypes.WORD),
		("wMonth", wintypes.WORD),
		("wDayOfWeek", wintypes.WORD),
		("wDay", wintypes.WORD),
		("wHour", wintypes.WORD),
		("wMinute", wintypes.WORD),
		("wSecond", wintypes.WORD),
		("wMilliseconds", wintypes.WORD),
	]


class BLUETOOTH_ADDRESS_UNION(ctypes.Union):
	_fields_ = [
		("ullLong", ctypes.c_ulonglong),
		("rgBytes", ctypes.c_ubyte * 6),
	]


class BLUETOOTH_ADDRESS(ctypes.Structure):
	_anonymous_ = ("address",)
	_fields_ = [("address", BLUETOOTH_ADDRESS_UNION)]


class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
	_fields_ = [("dwSize", wintypes.DWORD)]


class BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
	_fields_ = [
		("dwSize", wintypes.DWORD),
		("fReturnAuthenticated", wintypes.BOOL),
		("fReturnRemembered", wintypes.BOOL),
		("fReturnUnknown", wintypes.BOOL),
		("fReturnConnected", wintypes.BOOL),
		("fIssueInquiry", wintypes.BOOL),
		("cTimeoutMultiplier", ctypes.c_ubyte),
		("hRadio", wintypes.HANDLE),
	]


class BLUETOOTH_DEVICE_INFO(ctypes.Structure):
	_fields_ = [
		("dwSize", wintypes.DWORD),
		("Address", BLUETOOTH_ADDRESS),
		("ulClassofDevice", wintypes.ULONG),
		("fConnected", wintypes.BOOL),
		("fRemembered", wintypes.BOOL),
		("fAuthenticated", wintypes.BOOL),
		("stLastSeen", SYSTEMTIME),
		("stLastUsed", SYSTEMTIME),
		("szName", wintypes.WCHAR * 248),
	]


BluetoothFindFirstRadio = bthprops.BluetoothFindFirstRadio
BluetoothFindFirstRadio.argtypes = [
	ctypes.POINTER(BLUETOOTH_FIND_RADIO_PARAMS),
	ctypes.POINTER(wintypes.HANDLE),
]
BluetoothFindFirstRadio.restype = ctypes.c_void_p

BluetoothFindNextRadio = bthprops.BluetoothFindNextRadio
BluetoothFindNextRadio.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.HANDLE)]
BluetoothFindNextRadio.restype = wintypes.BOOL

BluetoothFindRadioClose = bthprops.BluetoothFindRadioClose
BluetoothFindRadioClose.argtypes = [ctypes.c_void_p]
BluetoothFindRadioClose.restype = wintypes.BOOL

BluetoothFindFirstDevice = bthprops.BluetoothFindFirstDevice
BluetoothFindFirstDevice.argtypes = [
	ctypes.POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
	ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
]
BluetoothFindFirstDevice.restype = ctypes.c_void_p

BluetoothFindNextDevice = bthprops.BluetoothFindNextDevice
BluetoothFindNextDevice.argtypes = [ctypes.c_void_p, ctypes.POINTER(BLUETOOTH_DEVICE_INFO)]
BluetoothFindNextDevice.restype = wintypes.BOOL

BluetoothFindDeviceClose = bthprops.BluetoothFindDeviceClose
BluetoothFindDeviceClose.argtypes = [ctypes.c_void_p]
BluetoothFindDeviceClose.restype = wintypes.BOOL

CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


@dataclass
class DeviceSnapshot:
	instance_id: str
	name: str
	address: str | None
	battery: int | None
	container_connected_setup: bool | None
	container_connected_cm: bool | None
	aep_connected_setup: bool | None
	devnode_status: int | None
	is_root: bool


def _read_setup_property(
	device_info_set: ctypes.c_void_p,
	devinfo: base.SP_DEVINFO_DATA,
	key: base.DEVPROPKEY,
) -> tuple[object | None, int | None]:
	prop_type = wintypes.ULONG(0)
	required_size = wintypes.DWORD(0)
	SetupDiGetDevicePropertyW(
		device_info_set,
		ctypes.byref(devinfo),
		ctypes.byref(key),
		ctypes.byref(prop_type),
		None,
		0,
		ctypes.byref(required_size),
		0,
	)
	last_error = ctypes.get_last_error()
	if last_error != base.ERROR_INSUFFICIENT_BUFFER or required_size.value == 0:
		return None, last_error

	buffer = (ctypes.c_byte * required_size.value)()
	if not SetupDiGetDevicePropertyW(
		device_info_set,
		ctypes.byref(devinfo),
		ctypes.byref(key),
		ctypes.byref(prop_type),
		buffer,
		required_size,
		ctypes.byref(required_size),
		0,
	):
		return None, ctypes.get_last_error()

	raw = bytes(buffer)
	if prop_type.value == DEVPROP_TYPE_BOOLEAN:
		return bool(raw[0]), 0
	if prop_type.value == DEVPROP_TYPE_UINT32:
		return int.from_bytes(raw[:4], "little"), 0
	return raw, 0


def _read_cm_property(instance_id: str, key: base.DEVPROPKEY) -> tuple[object | None, int]:
	devinst = wintypes.ULONG(0)
	cr = base.CM_Locate_DevNodeW(ctypes.byref(devinst), instance_id, base.CM_LOCATE_DEVNODE_NORMAL)
	if cr != base.CR_SUCCESS:
		return None, cr

	prop_type = wintypes.ULONG(0)
	required_size = wintypes.ULONG(0)
	cr = base.CM_Get_DevNode_PropertyW(
		devinst,
		ctypes.byref(key),
		ctypes.byref(prop_type),
		None,
		ctypes.byref(required_size),
		0,
	)
	if cr != CR_BUFFER_SMALL or required_size.value == 0:
		return None, cr

	buffer = (ctypes.c_byte * required_size.value)()
	cr = base.CM_Get_DevNode_PropertyW(
		devinst,
		ctypes.byref(key),
		ctypes.byref(prop_type),
		ctypes.byref(buffer),
		ctypes.byref(required_size),
		0,
	)
	if cr != base.CR_SUCCESS:
		return None, cr

	raw = bytes(buffer)
	if prop_type.value == DEVPROP_TYPE_BOOLEAN:
		return bool(raw[0]), cr
	if prop_type.value == DEVPROP_TYPE_UINT32:
		return int.from_bytes(raw[:4], "little"), cr
	if prop_type.value == base.DEVPROP_TYPE_BYTE:
		return raw[0], cr
	return raw, cr


def _format_bt_address(raw_bytes: ctypes.Array[ctypes.c_ubyte]) -> str:
	return "".join(f"{raw_bytes[index]:02X}" for index in range(5, -1, -1))


def _collect_classic_connection_flags() -> dict[str, dict[str, object]]:
	results: dict[str, dict[str, object]] = {}

	radio_params = BLUETOOTH_FIND_RADIO_PARAMS(dwSize=ctypes.sizeof(BLUETOOTH_FIND_RADIO_PARAMS))
	radio_handle = wintypes.HANDLE()
	radio_find_handle = BluetoothFindFirstRadio(ctypes.byref(radio_params), ctypes.byref(radio_handle))
	if not radio_find_handle:
		return results

	try:
		while True:
			search = BLUETOOTH_DEVICE_SEARCH_PARAMS(
				dwSize=ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS),
				fReturnAuthenticated=True,
				fReturnRemembered=True,
				fReturnUnknown=True,
				fReturnConnected=True,
				fIssueInquiry=False,
				cTimeoutMultiplier=0,
				hRadio=radio_handle,
			)
			device = BLUETOOTH_DEVICE_INFO(dwSize=ctypes.sizeof(BLUETOOTH_DEVICE_INFO))
			device_find_handle = BluetoothFindFirstDevice(ctypes.byref(search), ctypes.byref(device))
			if device_find_handle:
				try:
					while True:
						address = _format_bt_address(device.Address.rgBytes)
						results[address] = {
							"connected": bool(device.fConnected),
							"remembered": bool(device.fRemembered),
							"authenticated": bool(device.fAuthenticated),
							"name": device.szName.rstrip("\x00"),
						}
						if not BluetoothFindNextDevice(device_find_handle, ctypes.byref(device)):
							break
				finally:
					BluetoothFindDeviceClose(device_find_handle)

			CloseHandle(radio_handle)
			radio_handle = wintypes.HANDLE()
			if not BluetoothFindNextRadio(radio_find_handle, ctypes.byref(radio_handle)):
				break
	finally:
		if radio_handle:
			CloseHandle(radio_handle)
		BluetoothFindRadioClose(radio_find_handle)

	return results


def _decode_devnode_status(status: int | None) -> str:
	if status is None:
		return "n/a"

	flags: list[str] = []
	if status & DN_DRIVER_LOADED:
		flags.append("driver_loaded")
	if status & DN_STARTED:
		flags.append("started")
	if status & DN_DISABLEABLE:
		flags.append("disableable")
	if status & DN_REMOVABLE:
		flags.append("removable")
	if status & DN_NT_ENUMERATOR:
		flags.append("nt_enumerator")
	if status & DN_NT_DRIVER:
		flags.append("nt_driver")
	if status & DN_DEVICE_DISCONNECTED:
		flags.append("device_disconnected")

	flag_text = ",".join(flags) if flags else "no_known_flags"
	return f"0x{status:08X} ({flag_text})"


def _best_effort_connection(
	node: DeviceSnapshot,
	root: DeviceSnapshot | None,
	classic: dict[str, object] | None,
) -> str:
	for value in (
		node.container_connected_setup,
		node.container_connected_cm,
		node.aep_connected_setup,
		root.container_connected_setup if root else None,
		root.container_connected_cm if root else None,
		root.aep_connected_setup if root else None,
	):
		if value is True:
			return "connected"
		if value is False:
			return "disconnected"

	if classic is not None:
		return "connected" if classic["connected"] else "disconnected"

	status_values = [node.devnode_status]
	if root is not None:
		status_values.append(root.devnode_status)
	for status in status_values:
		if status is not None and status & DN_DEVICE_DISCONNECTED:
			return "disconnected"

	return "unknown"


def collect_bluetooth_connection_experiment() -> list[dict[str, object]]:
	device_info_set = base.SetupDiGetClassDevsW(None, None, None, base.DIGCF_PRESENT | base.DIGCF_ALLCLASSES)
	if not device_info_set or device_info_set == base.INVALID_HANDLE_VALUE:
		raise OSError(f"SetupDiGetClassDevsW failed: {ctypes.get_last_error()}")

	root_nodes: dict[str, DeviceSnapshot] = {}
	battery_nodes: list[DeviceSnapshot] = []

	try:
		index = 0
		while True:
			devinfo = base.SP_DEVINFO_DATA()
			devinfo.cbSize = ctypes.sizeof(base.SP_DEVINFO_DATA)
			if not base.SetupDiEnumDeviceInfo(device_info_set, index, ctypes.byref(devinfo)):
				if ctypes.get_last_error() == base.ERROR_NO_MORE_ITEMS:
					break
				raise OSError(f"SetupDiEnumDeviceInfo failed: {ctypes.get_last_error()}")

			index += 1
			instance_id = base._get_instance_id(device_info_set, devinfo)
			if not instance_id:
				continue

			upper_id = instance_id.upper()
			if not (
				upper_id.startswith("BTHENUM\\")
				or upper_id.startswith("BTHLE\\")
				or upper_id.startswith("BTHLEDEVICE\\")
			):
				continue

			name = base._read_device_name(device_info_set, devinfo) or instance_id
			address = base._extract_bt_address(instance_id)
			battery = base._read_battery_percent(instance_id)
			container_connected_setup, _ = _read_setup_property(
				device_info_set,
				devinfo,
				DEVPKEY_DEVICE_CONTAINER_IS_CONNECTED,
			)
			container_connected_cm, _ = _read_cm_property(instance_id, DEVPKEY_DEVICE_CONTAINER_IS_CONNECTED)
			aep_connected_setup, _ = _read_setup_property(device_info_set, devinfo, PKEY_DEVICES_AEP_IS_CONNECTED)
			devnode_status, _ = _read_cm_property(instance_id, DEVPKEY_DEVICE_DEVNODE_STATUS)

			snapshot = DeviceSnapshot(
				instance_id=instance_id,
				name=name,
				address=address,
				battery=battery,
				container_connected_setup=container_connected_setup if isinstance(container_connected_setup, bool) else None,
				container_connected_cm=container_connected_cm if isinstance(container_connected_cm, bool) else None,
				aep_connected_setup=aep_connected_setup if isinstance(aep_connected_setup, bool) else None,
				devnode_status=devnode_status if isinstance(devnode_status, int) else None,
				is_root=upper_id.startswith("BTHENUM\\DEV_") or upper_id.startswith("BTHLE\\DEV_"),
			)

			if snapshot.is_root and address:
				root_nodes[address] = snapshot
			if battery is not None:
				battery_nodes.append(snapshot)
	finally:
		base.SetupDiDestroyDeviceInfoList(device_info_set)

	classic_flags = _collect_classic_connection_flags()

	rows: list[dict[str, object]] = []
	for node in battery_nodes:
		root = root_nodes.get(node.address or "")
		display_name = root.name if root else node.name
		classic = classic_flags.get(node.address or "")
		rows.append(
			{
				"name": display_name,
				"battery": node.battery,
				"address": node.address,
				"best_effort_connection": _best_effort_connection(node, root, classic),
				"classic_api": classic,
				"node_container_connected_setup": node.container_connected_setup,
				"node_container_connected_cm": node.container_connected_cm,
				"node_aep_connected_setup": node.aep_connected_setup,
				"node_devnode_status": _decode_devnode_status(node.devnode_status),
				"root_name": root.name if root else None,
				"root_container_connected_setup": root.container_connected_setup if root else None,
				"root_container_connected_cm": root.container_connected_cm if root else None,
				"root_aep_connected_setup": root.aep_connected_setup if root else None,
				"root_devnode_status": _decode_devnode_status(root.devnode_status) if root else "n/a",
				"node_instance_id": node.instance_id,
				"root_instance_id": root.instance_id if root else None,
			}
		)

	return sorted(rows, key=lambda item: str(item["name"]).lower())


def main() -> int:
	sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	rows = collect_bluetooth_connection_experiment()
	if not rows:
		print("No Bluetooth battery information is available.")
		return 1

	for row in rows:
		print("=" * 72)
		print(f"Name: {row['name']}")
		print(f"Battery: {row['battery']}%")
		print(f"Address: {row['address'] or 'n/a'}")
		print(f"Best-effort connection: {row['best_effort_connection']}")
		print(f"Classic API: {row['classic_api']}")
		print(f"Node container connected (SetupAPI): {row['node_container_connected_setup']}")
		print(f"Node container connected (CfgMgr32): {row['node_container_connected_cm']}")
		print(f"Node AEP connected (SetupAPI): {row['node_aep_connected_setup']}")
		print(f"Node devnode status: {row['node_devnode_status']}")
		print(f"Root name: {row['root_name'] or 'n/a'}")
		print(f"Root container connected (SetupAPI): {row['root_container_connected_setup']}")
		print(f"Root container connected (CfgMgr32): {row['root_container_connected_cm']}")
		print(f"Root AEP connected (SetupAPI): {row['root_aep_connected_setup']}")
		print(f"Root devnode status: {row['root_devnode_status']}")
		print(f"Node instance: {row['node_instance_id']}")
		print(f"Root instance: {row['root_instance_id'] or 'n/a'}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
