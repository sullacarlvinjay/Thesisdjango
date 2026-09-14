import base64
import re
import zlib

_STREAM = re.compile(rb'stream(.*?)endstream', re.S)


def pdf_text(content):
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
