"""Read-only formatting policy for long evidence labels."""
from __future__ import annotations
import re

_LABEL_WIDTH_PATTERN = re.compile(r'(<td\s+)width=["\']39%["\']', re.I)

def constrain_detail_label_width(html: str, pixels: int = 280) -> str:
    """Keep evidence key-column width bounded on 4K/ultrawide windows."""
    width = max(120, min(420, int(pixels)))
    return _LABEL_WIDTH_PATTERN.sub(lambda match: match.group(1) + f'width="{width}"', html)
