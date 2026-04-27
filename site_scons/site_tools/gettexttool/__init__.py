"""This tool allows generation of gettext .mo compiled files, pot files from source code files
and pot files for merging.

Three new builders are added into the constructed environment:

- gettextMoFile: generates .mo file from .pot file using msgfmt.
- gettextPotFile: Generates .pot file from source code files.
- gettextMergePotFile: Creates a .pot file appropriate for merging into existing .po files.

To properly configure get text, define the following variables:

- gettext_package_bugs_address
- gettext_package_name
- gettext_package_version


"""

import ast
import shutil
import struct

from SCons.Action import Action


def exists(env):
	return True


XGETTEXT_COMMON_ARGS = (
	"--msgid-bugs-address='$gettext_package_bugs_address' "
	"--package-name='$gettext_package_name' "
	"--package-version='$gettext_package_version' "
	"--keyword=pgettext:1c,2 "
	"-c -o $TARGET $SOURCES"
)


def _decode_po_string(text: str) -> str:
	return ast.literal_eval(text)


def _parse_po_messages(po_path: str) -> dict[str, str]:
	messages: dict[str, str] = {}
	fuzzy = False
	msgctxt: str | None = None
	msgid: str | None = None
	msgid_plural: str | None = None
	msgstrs: dict[int, str] = {}
	current_field: tuple[str, int | None] | None = None

	def _commit():
		nonlocal fuzzy, msgctxt, msgid, msgid_plural, msgstrs, current_field
		if msgid is None or fuzzy:
			fuzzy = False
			msgctxt = None
			msgid = None
			msgid_plural = None
			msgstrs = {}
			current_field = None
			return

		key = msgid
		if msgctxt is not None:
			key = f"{msgctxt}\x04{key}"
		if msgid_plural is not None:
			key = f"{key}\x00{msgid_plural}"
			max_index = max(msgstrs, default=-1)
			value = "\x00".join(msgstrs.get(index, "") for index in range(max_index + 1))
		else:
			value = msgstrs.get(0, "")
		messages[key] = value

		fuzzy = False
		msgctxt = None
		msgid = None
		msgid_plural = None
		msgstrs = {}
		current_field = None

	with open(po_path, "r", encoding="utf-8") as po_file:
		for raw_line in po_file:
			line = raw_line.rstrip("\r\n")
			if not line:
				_commit()
				continue
			if line.startswith("#,"):
				if "fuzzy" in line:
					fuzzy = True
				continue
			if line.startswith("#"):
				continue
			if line.startswith("msgctxt "):
				msgctxt = _decode_po_string(line[8:])
				current_field = ("msgctxt", None)
				continue
			if line.startswith("msgid_plural "):
				msgid_plural = _decode_po_string(line[13:])
				current_field = ("msgid_plural", None)
				continue
			if line.startswith("msgid "):
				msgid = _decode_po_string(line[6:])
				current_field = ("msgid", None)
				continue
			if line.startswith("msgstr["):
				index_end = line.index("]")
				index = int(line[7:index_end])
				msgstrs[index] = _decode_po_string(line[index_end + 2 :])
				current_field = ("msgstr", index)
				continue
			if line.startswith("msgstr "):
				msgstrs[0] = _decode_po_string(line[7:])
				current_field = ("msgstr", 0)
				continue
			if line.startswith('"') and current_field is not None:
				extra = _decode_po_string(line)
				field_name, field_index = current_field
				if field_name == "msgctxt":
					msgctxt = (msgctxt or "") + extra
				elif field_name == "msgid":
					msgid = (msgid or "") + extra
				elif field_name == "msgid_plural":
					msgid_plural = (msgid_plural or "") + extra
				else:
					msgstrs[field_index or 0] = msgstrs.get(field_index or 0, "") + extra

	_commit()
	return messages


def _write_mo(messages: dict[str, str], mo_path: str) -> None:
	items = sorted(messages.items())
	ids = b""
	strs = b""
	offsets: list[tuple[int, int, int, int]] = []
	for msgid, msgstr in items:
		msgid_bytes = msgid.encode("utf-8")
		msgstr_bytes = msgstr.encode("utf-8")
		offsets.append((len(msgid_bytes), len(ids), len(msgstr_bytes), len(strs)))
		ids += msgid_bytes + b"\0"
		strs += msgstr_bytes + b"\0"

	num_strings = len(offsets)
	header_size = 7 * 4
	ids_table_offset = header_size
	strs_table_offset = ids_table_offset + num_strings * 8
	ids_pool_offset = strs_table_offset + num_strings * 8
	strs_pool_offset = ids_pool_offset + len(ids)

	with open(mo_path, "wb") as mo_file:
		mo_file.write(
			struct.pack(
				"<7I",
				0x950412DE,
				0,
				num_strings,
				ids_table_offset,
				strs_table_offset,
				0,
				0,
			)
		)
		for length, offset, _str_length, _str_offset in offsets:
			mo_file.write(struct.pack("<2I", length, ids_pool_offset + offset))
		for _length, _offset, str_length, str_offset in offsets:
			mo_file.write(struct.pack("<2I", str_length, strs_pool_offset + str_offset))
		mo_file.write(ids)
		mo_file.write(strs)


def _compile_mo(target, source, env):
	source_path = str(source[0])
	target_path = str(target[0])
	msgfmt = shutil.which("msgfmt")
	if msgfmt:
		import subprocess

		result = subprocess.run([msgfmt, "-o", target_path, source_path], check=False)
		return result.returncode

	messages = _parse_po_messages(source_path)
	_write_mo(messages, target_path)
	return 0


def generate(env):
	env.SetDefault(gettext_package_bugs_address="example@example.com")
	env.SetDefault(gettext_package_name="")
	env.SetDefault(gettext_package_version="")

	env["BUILDERS"]["gettextMoFile"] = env.Builder(
		action=Action(_compile_mo, "Compiling translation $SOURCE"),
		suffix=".mo",
		src_suffix=".po",
	)

	env["BUILDERS"]["gettextPotFile"] = env.Builder(
		action=Action("xgettext " + XGETTEXT_COMMON_ARGS, "Generating pot file $TARGET"),
		suffix=".pot",
	)

	env["BUILDERS"]["gettextMergePotFile"] = env.Builder(
		action=Action(
			"xgettext " + "--omit-header --no-location " + XGETTEXT_COMMON_ARGS,
			"Generating pot file $TARGET",
		),
		suffix=".pot",
	)
