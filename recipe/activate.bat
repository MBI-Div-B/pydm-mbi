@echo off
rem pydm-mbi: MBI stylesheet and shared components for PyDM and Qt Designer.
rem The dark stylesheet is the default; set PYDM_MBI_THEME=light before activating for the light one.
set "_PYDM_MBI_DIR=%CONDA_PREFIX%\Lib\site-packages\pydm_mbi"
if not exist "%_PYDM_MBI_DIR%" goto :done
set "_PYDM_MBI_OLD_STYLESHEET=%PYDM_STYLESHEET%"
set "_PYDM_MBI_OLD_INCLUDE_DEFAULT=%PYDM_STYLESHEET_INCLUDE_DEFAULT%"
set "_PYDM_MBI_OLD_DISPLAYS_PATH=%PYDM_DISPLAYS_PATH%"
if /i "%PYDM_MBI_THEME%"=="light" (
    set "PYDM_STYLESHEET=%_PYDM_MBI_DIR%\style\mbi-light.qss"
) else (
    set "PYDM_STYLESHEET=%_PYDM_MBI_DIR%\style\mbi.qss"
)
set "PYDM_STYLESHEET_INCLUDE_DEFAULT=1"
if defined PYDM_DISPLAYS_PATH (
    set "PYDM_DISPLAYS_PATH=%_PYDM_MBI_DIR%\components;%PYDM_DISPLAYS_PATH%"
) else (
    set "PYDM_DISPLAYS_PATH=%_PYDM_MBI_DIR%\components"
)
:done
set "_PYDM_MBI_DIR="
