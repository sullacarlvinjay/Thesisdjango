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
    pass


class ConversionFailed(RuntimeError):
    pass


def soffice_path():
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

    path = os.path.join(str(settings.BASE_DIR), '.report_cache')
    os.makedirs(path, exist_ok=True)
    marker = os.path.join(path, '.gitignore')
    if not os.path.exists(marker):
        with open(marker, 'w', encoding='utf-8') as handle:
            handle.write('*\n')
    return path


def to_pdf(data, suffix):
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

    partial = f'{cached}.{os.getpid()}.part'
    with open(partial, 'wb') as handle:
        handle.write(pdf)
    os.replace(partial, cached)
    return pdf
