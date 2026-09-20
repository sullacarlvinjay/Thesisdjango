import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

SOURCE = os.path.join('media', 'logos', 'BiPSU.png')
DESTINATION = os.path.join('static', 'img')

ICO_SIZES = [(16, 16), (32, 32), (48, 48)]
PNG_32 = 32
APPLE_TOUCH = 180


class Command(BaseCommand):
    help = 'Rebuild static/img/ tab icons from the BiPSU seal.'

    def handle(self, *args, **options):
        try:
            from PIL import Image
        except ImportError as missing:
            raise CommandError('Pillow is not installed.') from missing

        source = os.path.join(settings.BASE_DIR, SOURCE)
        out = os.path.join(settings.BASE_DIR, DESTINATION)
        if not os.path.exists(source):
            raise CommandError(f'No seal at {SOURCE}.')
        os.makedirs(out, exist_ok=True)

        seal = Image.open(source).convert('RGBA')

        seal = seal.crop(seal.getchannel('A').getbbox())
        side = max(seal.size)
        square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
        square.paste(seal, ((side - seal.width) // 2, (side - seal.height) // 2))

        def scaled(px):
            return square.resize((px, px), Image.LANCZOS)

        written = [
            ('favicon.ico', lambda p: scaled(max(s[0] for s in ICO_SIZES)).save(p, sizes=ICO_SIZES)),
            ('favicon-32.png', lambda p: scaled(PNG_32).save(p)),
            ('apple-touch-icon.png', lambda p: scaled(APPLE_TOUCH).save(p)),
        ]
        for name, write in written:
            path = os.path.join(out, name)
            write(path)
            self.stdout.write(f'  {name}  {os.path.getsize(path):,} bytes')

        self.stdout.write(self.style.SUCCESS(
            'Tab icons rebuilt. Run collectstatic before deploying, and bump '
            'the ?v= on the links in templates/_favicon.html so browsers that '
            'cached the old icon fetch the new one.'))
