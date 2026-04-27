# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.

from site_scons.site_tools.NVDATool.typings import (
	AddonInfo,
	BrailleTables,
	SpeechDictionaries,
	SymbolDictionaries,
)

# Since some strings in `addon_info` are translatable,
# we need to include them in the .po files.
# Gettext recognizes only strings given as parameters to the `_` function.
# To avoid initializing translations in this module we simply import a "fake" `_` function
# which returns whatever is given to it as an argument.
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	# add-on Name/identifier, internal for NVDA
	addon_name="BlueToothBatteryReport",
	# Add-on summary/title, usually the user visible name of the add-on
	# Translators: Summary/title for this add-on
	# to be shown on installation and add-on information found in add-on store
	addon_summary=_("BlueToothBatteryReport"),
	# Add-on description
	# Translators: Long description to be shown for this add-on on add-on information from add-on store
	addon_description=_("Use the NVDA+Shift+= hotkey to report Bluetooth device battery levels."),
	# version
	addon_version="0.3",
	# Author(s)
	addon_author="codex",
	# URL for the add-on documentation support
	addon_url="https://www.zxrjy.net/",
	# Documentation file name
	addon_docFileName="readme.html",
	# Minimum NVDA version supported (e.g. "2019.3.0", minor version is optional)
	addon_minimumNVDAVersion="2025.1.0",
	# Last NVDA version supported/tested (e.g. "2024.4.0", ideally more recent than minimum version)
	addon_lastTestedNVDAVersion="2026.1.0",
	# Add-on update channel (default is None, denoting stable releases,
	# and for development releases, use "dev".)
	# Do not change unless you know what you are doing!
	addon_updateChannel=None,
)

# Define the python files that are the sources of your add-on.
# You can either list every file (using ""/") as a path separator,
# or use glob expressions.
# For example to include all files with a ".py" extension from the "globalPlugins" dir of your add-on
# the list can be written as follows:
# pythonSources = ["addon/globalPlugins/*.py"]
# For more information on SCons Glob expressions please take a look at:
# https://scons.org/doc/production/HTML/scons-user/apd.html
pythonSources: list[str] = ["addon/globalPlugins/*.py"]

# Files that contain strings for translation. Usually your python sources
i18nSources: list[str] = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
# You can either list every file (using ""/") as a path separator,
# or use glob expressions.
excludedFiles: list[str] = [
	"globalPlugins/__pycache__/*",
]

# Base language for the NVDA add-on
baseLanguage: str = "en"

# Markdown extensions for add-on documentation
markdownExtensions: list[str] = []

# Custom braille translation tables
brailleTables: BrailleTables = {}

# Custom speech symbol dictionaries
symbolDictionaries: SymbolDictionaries = {}

# Custom speech dictionaries (distinct from symbol dictionaries above)
speechDictionaries: SpeechDictionaries = {}
