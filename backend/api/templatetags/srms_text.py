import re

from django import template

register = template.Library()

_SENTENCE_START = re.compile(r"(\A\s*|(?<=[.!?])[\"')\]]?\s+)([a-z])")


@register.filter
def sentence_case(value):
    if value is None:
        return ''
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), str(value))
