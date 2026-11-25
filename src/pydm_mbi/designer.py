"""Qt Designer plugins, registered through the "pydm.widget" entry point in pyproject.toml."""

from pydm.widgets.qtplugin_base import qtplugin_factory
from pydm.widgets.qtplugin_extensions import BasicSettingsExtension, RulesExtension

from .widgets import MbiHeartbeat, MbiLogo, TangoStateLed

GROUP = "MBI Div B"
EXTENSIONS = [BasicSettingsExtension, RulesExtension]

TangoStateLedPlugin = qtplugin_factory(TangoStateLed, group=GROUP, extensions=EXTENSIONS)
MbiLogoPlugin = qtplugin_factory(MbiLogo, group=GROUP)
MbiHeartbeatPlugin = qtplugin_factory(MbiHeartbeat, group=GROUP, extensions=EXTENSIONS)
