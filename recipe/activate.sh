# pydm-mbi: MBI stylesheet and shared components for PyDM and Qt Designer.
# The dark stylesheet is the default; set PYDM_MBI_THEME=light before activating for the light one.
# The package is noarch, so its folder is found by a glob instead of a fixed Python version.
for _pydm_mbi_dir in "$CONDA_PREFIX"/lib/python3*/site-packages/pydm_mbi; do
    if [ -d "$_pydm_mbi_dir" ]; then
        export _PYDM_MBI_OLD_STYLESHEET="${PYDM_STYLESHEET-}"
        export _PYDM_MBI_OLD_INCLUDE_DEFAULT="${PYDM_STYLESHEET_INCLUDE_DEFAULT-}"
        export _PYDM_MBI_OLD_DISPLAYS_PATH="${PYDM_DISPLAYS_PATH-}"
        if [ "${PYDM_MBI_THEME-}" = "light" ]; then
            export PYDM_STYLESHEET="$_pydm_mbi_dir/style/mbi-light.qss"
        else
            export PYDM_STYLESHEET="$_pydm_mbi_dir/style/mbi.qss"
        fi
        export PYDM_STYLESHEET_INCLUDE_DEFAULT=1
        export PYDM_DISPLAYS_PATH="$_pydm_mbi_dir/components${PYDM_DISPLAYS_PATH:+:$PYDM_DISPLAYS_PATH}"
        break
    fi
done
unset _pydm_mbi_dir
