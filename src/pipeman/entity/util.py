from __future__ import annotations
import typing as t

import markupsafe

from pipeman.i18n import gettext

if t.TYPE_CHECKING:
    from pipeman.i18n import MultiLanguageString


class HtmlList:

    def __init__(self, items):
        self.items = items

    def __str__(self):
        h = '<ul>'
        for item in self.items:
            h += f'<li>{markupsafe.escape(item)}</li>'
        h += '</ul>'
        return markupsafe.Markup(h)


def _render_mls(mls: MultiLanguageString):
    keys = [k for k in mls if (not k[0] == '_') and mls[k]]
    if len(keys) == 1 and keys[0] == 'und':
        return markupsafe.escape(mls['und'])
    html = '<dl>'
    for key in keys:
        if key != 'und':
            html += f'<dt>{gettext(f"languages.full.{key}")}</dt><dd>{markupsafe.escape(mls[key])}</dd>'
    if 'und' in keys:
        html += f'<dt>{gettext(f"languages.full.und")}</dt><dd>{markupsafe.escape(mls["und"])}</dd>'

    html += '</dl>'
    return markupsafe.Markup(html)

