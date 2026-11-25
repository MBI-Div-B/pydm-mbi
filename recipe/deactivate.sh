_pydm_mbi_restore() {
    # $1: variable, $2: saved value
    if [ -n "$2" ]; then
        export "$1=$2"
    else
        unset "$1"
    fi
}
_pydm_mbi_restore PYDM_STYLESHEET "${_PYDM_MBI_OLD_STYLESHEET-}"
_pydm_mbi_restore PYDM_STYLESHEET_INCLUDE_DEFAULT "${_PYDM_MBI_OLD_INCLUDE_DEFAULT-}"
_pydm_mbi_restore PYDM_DISPLAYS_PATH "${_PYDM_MBI_OLD_DISPLAYS_PATH-}"
unset _PYDM_MBI_OLD_STYLESHEET _PYDM_MBI_OLD_INCLUDE_DEFAULT _PYDM_MBI_OLD_DISPLAYS_PATH
unset -f _pydm_mbi_restore
