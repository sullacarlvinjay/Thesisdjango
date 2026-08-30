"""Helpers shared by the test modules. No tests of its own.

``pdf_text`` exists so a test can assert that a name actually reached the page
an officer reads, rather than stopping at "the view returned a PDF". ReportLab
ASCII85-encodes and deflates its content streams, so the text has to be pulled
back out before it can be searched.

It reads ReportLab's own output only. A PDF that came out of LibreOffice
carries subset fonts with custom encodings, so its strings are glyph codes
rather than letters — a test that wants readable text has to pin the view to
the ReportLab path first.
"""
import base64
import re
import zlib

_STREAM = re.compile(rb'stream(.*?)endstream', re.S)


def pdf_text(content):
    """Every content stream in a PDF, inflated and joined into one string.

    Text comes back with PDF operators around it — assert with ``in``, not by
    equality. A stream that cannot be decoded (an embedded image, say) is
    skipped rather than failing the read.
    """
    chunks = []
    for match in _STREAM.finditer(content):
        raw = match.group(1).strip(b'\r\n')
        for decode in (
            lambda b: zlib.decompress(base64.a85decode(b, adobe=True)),
            zlib.decompress,
            lambda b: base64.a85decode(b, adobe=True),
        ):
            try:
                chunks.append(decode(raw))
                break
            except Exception:
                continue
    return b'\n'.join(chunks).decode('latin-1')
