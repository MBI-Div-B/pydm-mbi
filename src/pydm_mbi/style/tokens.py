"""
Design tokens: the single source for colors and fonts.

They follow the MBI design guide (2026 logo redesign) and its slide template:
dark slate background with a slight vertical gradient, Fira Sans (headings medium, text light),
four highlight colors and four extended colors. mbistyles (https://github.com/MBI-Div-B/mbistyles)
uses the same palette for matplotlib.

Widgets read the tokens directly; the stylesheets are generated from mbi.qss.in with
`python -m pydm_mbi.style`.
"""

FONT_FAMILY = "Fira Sans"
WEIGHT_TEXT = 300  # light
WEIGHT_HEADING = 500  # medium
WEIGHT_EMPHASIS = 600  # semi-bold, e.g. important messages

BASE = "#3C415A"  # base color of the design guide
LIGHT_BASE = "#F2F2F2"

HIGHLIGHT = {
    "blue": "#3672B2",
    "cyan": "#2AB5DD",
    "magenta": "#CF0EEE",
    "violet": "#7E5FCC",
}
EXTENDED = {
    "green": "#45BA47",
    "yellow": "#F2E029",
    "orange": "#ED590C",
    "red": "#D71045",
}
PALETTE = {**HIGHLIGHT, **EXTENDED}

THEMES = {
    # Default for the (usually dark) laser labs, as the dark slides
    "dark": {
        "background_top": "#222533",
        "background_bottom": BASE,
        "surface": "#454A63",  # panels and buttons, a step above the base color
        "input": "#2B2F40",
        "text": LIGHT_BASE,
        "muted": "#A4A8B8",
        "border": "#5A5F78",
        "accent": HIGHLIGHT["cyan"],  # sub-headings and focus in the dark slides
        "accent_text": "#222533",
        "primary": HIGHLIGHT["blue"],
        "important": HIGHLIGHT["magenta"],
    },
    "light": {
        "background_top": "#FFFFFF",
        "background_bottom": "#FFFFFF",
        "surface": LIGHT_BASE,
        "input": "#FFFFFF",
        "text": BASE,
        "muted": "#6E7287",
        "border": "#D5D7DE",
        "accent": HIGHLIGHT["blue"],
        "accent_text": "#FFFFFF",
        "primary": HIGHLIGHT["blue"],
        "important": HIGHLIGHT["magenta"],
    },
}

# Usual Tango colors for DevState, by state name
STATE_COLORS = {
    "ON": "#00FF00",
    "OFF": "#FFFFFF",
    "CLOSE": "#FFFFFF",
    "OPEN": "#00FF00",
    "INSERT": "#FFFFFF",
    "EXTRACT": "#00FF00",
    "MOVING": "#80A0FF",
    "STANDBY": "#FFFF00",
    "FAULT": "#FF0000",
    "INIT": "#CCCC7A",
    "RUNNING": "#007D00",
    "ALARM": "#FF8C00",
    "DISABLE": "#FF00FF",
    "UNKNOWN": "#9B9B9B",
}
DISCONNECTED_COLOR = "#5D5D5D"
