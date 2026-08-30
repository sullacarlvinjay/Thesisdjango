"""Turn the office's own .docx / .xlsx into a PDF, for previewing on screen.

The Reports tabs are meant to show the actual document each office files — the
Word masterlist and the CHED Annex 2 workbook — rather than a redrawing of it,
so the very bytes the download produces are what get converted here.

LibreOffice does the conversion. It reads both formats, runs headless, and
behaves the same on a Windows desktop and on a Linux host. Word and Excel
automation was tried and rejected: Excel refuses COM calls under a Click-to-Run
install, and a failed run strands an invisible WINWORD.EXE holding the office
template locked — not something a page view should be able to do.

Converting costs a second or two, so a result is cached under a digest of the
source bytes: the same masterlist previews instantly until a record changes.

When LibreOffice is not installed the callers fall back to ``report_pdf``,
which lays the same rows out itself, and the page says so. The download is the
real document either way.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

TIMEOUT_SECONDS = 90

# Looked at in order. The environment variable comes first so a host can point
# at an install none of the well-known paths cover.
ENV_VAR = 'SOFFICE_PATH'
WINDOWS_PATHS = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
]
MAC_PATHS = ['/Applications/LibreOffice.app/Contents/MacOS/soffice']
POSIX_NAMES = ['soffice', 'libreoffice']


class ConversionUnavailable(RuntimeError):
    """No LibreOffice on this machine — the caller should fall back."""


class ConversionFailed(RuntimeError):
    """LibreOffice is installed but did not produce a PDF."""


def soffice_path():
    """The LibreOffice executable, or None if this machine has none."""
    override = os.environ.get(ENV_VAR)
    if override and os.path.exists(override):
        return override

    for name in POSIX_NAMES:
        found = shutil.which(name)
        if found:
            return found

    candidates = WINDOWS_PATHS if sys.platform == 'win32' else MAC_PATHS
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def available():
    return soffice_path() is not None


def _cache_dir():
    from django.conf import settings

    # Deliberately outside MEDIA_ROOT: in DEBUG that directory is served, and a
    # scholars masterlist is not something to leave behind a guessable URL.
    path = os.path.join(str(settings.BASE_DIR), '.report_cache')
    os.makedirs(path, exist_ok=True)
    # The project has no .gitignore, so the cache ignores itself rather than
    # having converted reports turn up in someone's next commit.
    marker = os.path.join(path, '.gitignore')
    if not os.path.exists(marker):
        with open(marker, 'w', encoding='utf-8') as handle:
            handle.write('*\n')
    return path


def to_pdf(data, suffix):
    """Convert document bytes to PDF bytes.

    ``suffix`` is the source extension ('.docx', '.xlsx'). Raises
    ConversionUnavailable when LibreOffice is missing, ConversionFailed when it
    is present but the conversion did not come out.
    """
    executable = soffice_path()
    if executable is None:
        raise ConversionUnavailable(
            'LibreOffice is not installed, so the office document cannot be '
            'converted for preview.')

    digest = hashlib.sha256(suffix.encode() + data).hexdigest()
    cached = os.path.join(_cache_dir(), f'{digest}.pdf')
    if os.path.exists(cached):
        with open(cached, 'rb') as handle:
            return handle.read()

    with tempfile.TemporaryDirectory(prefix='srms-convert-') as work:
        source = os.path.join(work, f'report{suffix}')
        with open(source, 'wb') as handle:
            handle.write(data)

        # Its own profile directory, so a copy of LibreOffice the user already
        # has open cannot make this call return without converting anything.
        profile = os.path.join(work, 'profile')
        command = [
            executable,
            f'-env:UserInstallation=file:///{profile.replace(os.sep, "/")}',
            '--headless', '--norestore', '--nolockcheck', '--nodefault',
            '--convert-to', 'pdf', '--outdir', work, source,
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise ConversionFailed(
                f'LibreOffice did not finish converting within '
                f'{TIMEOUT_SECONDS} seconds.')

        produced = os.path.join(work, 'report.pdf')
        if not os.path.exists(produced):
            detail = (result.stderr or result.stdout or b'').decode(
                'utf-8', 'replace').strip()
            raise ConversionFailed(
                f'LibreOffice produced no PDF (exit {result.returncode}). '
                f'{detail}'.strip())

        with open(produced, 'rb') as handle:
            pdf = handle.read()

    # Written beside the cache and moved into place, so a reader never opens a
    # half-written file.
    partial = f'{cached}.{os.getpid()}.part'
    with open(partial, 'wb') as handle:
        handle.write(pdf)
    os.replace(partial, cached)
    return pdf
