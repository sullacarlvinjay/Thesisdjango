"""Converting office documents to PDF with LibreOffice.

Used for the masterlist preview, so the office sees its own DOCX template
rendered exactly rather than an approximation. LibreOffice is not installed on
the deployed container, so every caller has to cope with it being absent —
``available()`` says so, and the reports fall back to the ReportLab layout.

Conversions are cached by a hash of the input, because the same report is
previewed repeatedly while it is read.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

TIMEOUT_SECONDS = 90

ENV_VAR = 'SOFFICE_PATH'
WINDOWS_PATHS = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
]
MAC_PATHS = ['/Applications/LibreOffice.app/Contents/MacOS/soffice']
POSIX_NAMES = ['soffice', 'libreoffice']


class ConversionUnavailable(RuntimeError):
    """Raised when LibreOffice is not installed at all."""
    pass


class ConversionFailed(RuntimeError):
    """Raised when LibreOffice ran but produced no PDF."""
    pass


def soffice_path():
    """Locate the LibreOffice executable, or ``None``.

    Checked at call time rather than at import: the deployed container
    does not have it, and the application has to start there anyway.
    """
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
    """Whether a DOCX can be converted to PDF on this machine."""
    return soffice_path() is not None


def _cache_dir():
    """The on-disk conversion cache, created if needed.

    Writes its own ``.gitignore`` so a developer's rendered reports never
    reach a commit.
    """
    from django.conf import settings

    path = os.path.join(str(settings.BASE_DIR), '.report_cache')
    os.makedirs(path, exist_ok=True)
    marker = os.path.join(path, '.gitignore')
    if not os.path.exists(marker):
        with open(marker, 'w', encoding='utf-8') as handle:
            handle.write('*\n')
    return path


def to_pdf(data, suffix):
    """Convert an office document to PDF bytes.

    Cached by a hash of the input, because conversion takes seconds and
    the same masterlist is previewed repeatedly while the office reads it.
    The cache is written to a temporary name and renamed into place, so a
    reader never opens a half-written PDF.

    Each run gets a private LibreOffice profile in a throwaway directory:
    two conversions at once would otherwise fight over the shared one.

    Raises:
        ConversionUnavailable: LibreOffice is not installed.
        ConversionFailed: it ran but produced nothing, or timed out.
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
        except subprocess.TimeoutExpired as expired:
            raise ConversionFailed(
                f'LibreOffice did not finish converting within '
                f'{TIMEOUT_SECONDS} seconds.') from expired

        produced = os.path.join(work, 'report.pdf')
        if not os.path.exists(produced):
            detail = (result.stderr or result.stdout or b'').decode(
                'utf-8', 'replace').strip()
            raise ConversionFailed(
                f'LibreOffice produced no PDF (exit {result.returncode}). '
                f'{detail}'.strip())

        with open(produced, 'rb') as handle:
            pdf = handle.read()

    partial = f'{cached}.{os.getpid()}.part'
    with open(partial, 'wb') as handle:
        handle.write(pdf)
    os.replace(partial, cached)
    return pdf
