"""Text filters for prose the office typed, printed the way it should read.

Everything here leaves the words alone. A scholarship description is written by
whoever set the programme up, in a textarea, at speed — the filters below fix
how it is *presented* without editing what it says, because a filter that
rewrote the office's wording would be a filter nobody could trust with a
programme name.
"""
import re

from django import template

register = template.Library()

# The first letter of the text, and the first letter after a sentence has ended.
# A sentence ends at . ! or ? — optionally closed by a quote or a bracket —
# followed by whitespace. The letter itself is group 2 so the run in front of it
# can be put back untouched.
_SENTENCE_START = re.compile(r"(\A\s*|(?<=[.!?])[\"')\]]?\s+)([a-z])")


@register.filter
def sentence_case(value):
    """Capitalise the first letter of every sentence, and nothing else.

    Deliberately not ``.capitalize()`` or ``|title``: both rewrite the rest of
    the line, and this text is full of things that are already spelled the way
    they are meant to be — CHED, DOST, TES, BiPSU, UniFAST, RA 7687. Only a
    lowercase letter in a sentence-opening position is touched, so a description
    typed as "the CHED grant. it covers tuition" reads as "The CHED grant. It
    covers tuition" with both acronyms intact.

    An abbreviation mid-sentence ("e.g. this one") will capitalise after the
    full stop. That is the cost of not keeping a dictionary of abbreviations,
    and it is the smaller error of the two.
    """
    if value is None:
        return ''
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), str(value))
