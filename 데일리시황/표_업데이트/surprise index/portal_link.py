"""Keep the independent Surprise entry in both existing and regenerated portals."""
import os
import re
from pathlib import Path
from html import escape

START = '<!-- surprise-index:start -->'
END = '<!-- surprise-index:end -->'

def add_portal_link(page, destination):
    destination = Path(destination).resolve()
    target = next((p/'surprise index/index.html' for p in destination.parents
                   if (p/'surprise index/index.html').exists()), None)
    if target is None:
        return page
    href = escape(os.path.relpath(target, destination.parent).replace(os.sep, '/'))
    content = f'<div class="row"><div class="name">Citi Surprise Index<br/><small>국가별 그래프 · 히트맵 | 경기 5DMA · 물가 월별</small></div><div class="links"><a href="{href}#economic">Economic</a><a href="{href}#inflation">Inflation</a></div></div>'
    block = START + content + END
    if START in page:
        return re.sub(re.escape(START)+'.*?'+re.escape(END), lambda _: block, page, flags=re.S)
    if '</main>' in page:
        return page.replace('</main>', block+'</main>', 1)
    if '</ul>' in page:
        item = START + f'<li><a href="{href}">Citi Surprise Index · 국가별 경기 5DMA / 물가 월별 · 그래프와 히트맵</a></li>' + END
        return page.replace('</ul>', item+'</ul>', 1)
    return page.replace('</body>', block+'</body>', 1)
