@echo off
setlocal

where py >nul 2>nul
if errorlevel 1 (
	echo Python launcher not found. Please install Python 3.10 or later.
	exit /b 1
)

py -3 -c "import markdown, SCons" >nul 2>nul
if errorlevel 1 (
	echo Missing build dependencies.
	echo Run: py -m pip install scons markdown
	exit /b 1
)

scons -Q
exit /b %errorlevel%
