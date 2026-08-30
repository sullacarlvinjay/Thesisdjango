"""The two office reports rendered as a PDF page, for the Reports tabs.

Each office files a document — the SDSO its Word masterlist, UniFAST the CHED
Annex 2 workbook — so the tab that previews one shows a laid-out page rather
than a web table an officer has to imagine on paper. Both PDFs are built from
the same row builders the downloads use (``masterlist_report.build_context``
and ``tes_report.grantee_rows``), so what is on screen and what leaves the
office cannot drift apart.

Nothing here is a second source of truth: column headings, row order and cell
contents all come from those modules. This file only decides how they sit on
a page.
"""
import os
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    CondPageBreak, Image, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

PAGE_SIZE = landscape(legal)
MARGIN = 0.4 * inch
CONTENT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN

# The office forms' own fills, so a printed preview matches the workbook and
# the Word document it stands in for.
HEADER_BG = colors.HexColor('#D9E1F2')
SECTION_BG = colors.HexColor('#BDD7EE')
STRIPE_BG = colors.HexColor('#F5F7FF')
GRID = colors.HexColor('#94A3B8')

_STYLES = getSampleStyleSheet()


def _style(name, **kwargs):
    return ParagraphStyle(name, parent=_STYLES['Normal'], **kwargs)


TITLE = _style('rp-title', fontName='Helvetica-Bold', fontSize=12,
               alignment=TA_CENTER, leading=15)
SUBTITLE = _style('rp-subtitle', fontSize=9, alignment=TA_CENTER, leading=12)
PERIOD = _style('rp-period', fontName='Helvetica-Bold', fontSize=10.5,
                alignment=TA_CENTER, leading=14, spaceBefore=4)
LEGEND = _style('rp-legend', fontName='Helvetica-Oblique', fontSize=7.5,
                alignment=TA_CENTER, leading=10)
SECTION = _style('rp-section', fontName='Helvetica-Bold', fontSize=9,
                 alignment=TA_CENTER, leading=12)
GROUP = _style('rp-group', fontName='Helvetica-Bold', fontSize=8,
               alignment=TA_LEFT, leading=11, spaceBefore=4)
NOTE = _style('rp-note', fontSize=7.5, leading=10)
NOTE_HEAD = _style('rp-note-head', fontName='Helvetica-Bold', fontSize=7.5,
                   leading=10)
CELL = _style('rp-cell', fontSize=6, alignment=TA_CENTER, leading=7.5)
CELL_HEAD = _style('rp-cell-head', fontName='Helvetica-Bold', fontSize=6,
                   alignment=TA_CENTER, leading=7.5)
EMPTY = _style('rp-empty', fontName='Helvetica-Oblique', fontSize=7,
               alignment=TA_CENTER, textColor=colors.HexColor('#94A3B8'))
SIGN_LABEL = _style('rp-sign-label', fontSize=7,
                    textColor=colors.HexColor('#475569'), leading=10)
SIGN_NAME = _style('rp-sign-name', fontName='Helvetica-Bold', fontSize=7.5,
                   leading=10, spaceBefore=22)
SIGN_ROLE = _style('rp-sign-role', fontSize=6.5, leading=9)
STANDIN = _style('rp-standin', fontName='Helvetica-Bold', fontSize=7,
                 alignment=TA_CENTER, leading=9,
                 textColor=colors.HexColor('#92400E'))

# Printed at the head of every page built here, because these pages stand in
# for the office's own file. Whoever is looking at the frame should be able to
# tell that from the frame, not only from the tab around it.
STANDIN_NOTICE = (
    'STAND-IN LAYOUT — not the office template. Install LibreOffice on the '
    'server to preview the document itself; the download is always the real file.'
)

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'media', 'logos', 'BiPSU.png',
)


def _text(value):
    """A cell value as printable text — dates and blanks included."""
    if value is None or value == '':
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%m/%d/%Y')
    return str(value)


def _cell(value, style=CELL):
    return Paragraph(escape(_text(value)), style)


def _column_widths(headers, rows, total=CONTENT_WIDTH):
    """Widths in proportion to what each column actually has to hold.

    Equal columns waste half the page on SEX and YR. while a course name wraps
    over six lines, so each column is weighted by its longest value — capped,
    so one stray long entry cannot squeeze the rest off the page.
    """
    weights = []
    for i, header in enumerate(headers):
        longest_word = max((len(w) for w in _text(header).split()), default=4)
        content = max((len(_text(r[i])) for r in rows if i < len(r)), default=0)
        weights.append(min(max(longest_word, content, 4), 26))
    scale = total / sum(weights) if weights else 1
    return [w * scale for w in weights]


def _table(headers, rows, widths=None):
    """One report table: heading row repeated on every page, zebra body."""
    data = [[_cell(h, CELL_HEAD) for h in headers]]
    for row in rows:
        data.append([_cell(v) for v in row])
    if not rows:
        data.append([Paragraph('No records', EMPTY)] + [''] * (len(headers) - 1))

    table = Table(
        data,
        colWidths=widths or _column_widths(headers, rows),
        repeatRows=1,
        hAlign='LEFT',
    )
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('GRID', (0, 0), (-1, -1), 0.4, GRID),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, STRIPE_BG]),
    ]
    if not rows:
        style.append(('SPAN', (0, 1), (-1, 1)))
    table.setStyle(TableStyle(style))
    return table


def _banner(text):
    """The pale blue strip a programme's table sits under."""
    banner = Table([[Paragraph(escape(text), SECTION)]],
                   colWidths=[CONTENT_WIDTH], hAlign='LEFT')
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SECTION_BG),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return banner


_LOGO_CACHE = {}


def _logo(size=0.55 * inch):
    """The university seal, scaled down once and kept.

    The source file is several megabytes at 1563px square; embedded whole it
    would make every preview a multi-megabyte download for a half-inch mark.
    A missing or unreadable seal is cosmetic, so the letterhead goes out
    without it rather than failing the report.
    """
    if not os.path.exists(LOGO_PATH):
        return None
    if 'png' not in _LOGO_CACHE:
        try:
            from PIL import Image as PILImage

            source = PILImage.open(LOGO_PATH).convert('RGBA')
            source.thumbnail((220, 220), PILImage.LANCZOS)
            # Flattened onto white: the page is paper, and reportlab would
            # otherwise print the transparent ground black.
            flat = PILImage.new('RGB', source.size, 'white')
            flat.paste(source, mask=source.split()[-1])
            buf = BytesIO()
            flat.save(buf, format='PNG', optimize=True)
            _LOGO_CACHE['png'] = buf.getvalue()
        except Exception:
            _LOGO_CACHE['png'] = None
    if not _LOGO_CACHE['png']:
        return None

    image = Image(BytesIO(_LOGO_CACHE['png']), width=size, height=size)
    image.hAlign = 'CENTER'
    return image


def _letterhead(lines, legend=None):
    story = [Paragraph(escape(STANDIN_NOTICE), STANDIN), Spacer(1, 6)]
    if legend:
        story.append(Paragraph(escape(legend), LEGEND))
    seal = _logo()
    if seal is not None:
        story.append(seal)
    for text, style in lines:
        story.append(Paragraph(escape(text), style))
    story.append(Spacer(1, 10))
    return story


def _signatories(blocks):
    """The office's signature blocks, side by side across the page."""
    width = CONTENT_WIDTH / len(blocks)
    columns = []
    for label, name, role in blocks:
        column = Table(
            [[Paragraph(escape(label), SIGN_LABEL)],
             [Paragraph(escape(name), SIGN_NAME)],
             [Paragraph(escape(role), SIGN_ROLE)]],
            colWidths=[width - 12],
        )
        column.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        columns.append(column)

    row = Table([columns], colWidths=[width] * len(columns), hAlign='LEFT')
    row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return [Spacer(1, 22), row]


def _page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.HexColor('#64748B'))
    canvas.drawRightString(PAGE_SIZE[0] - MARGIN, 0.28 * inch,
                           f'Page {canvas.getPageNumber()}')
    canvas.restoreState()


def _build(story, title):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=PAGE_SIZE,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.45 * inch, bottomMargin=0.45 * inch,
        title=title, author='BiPSU SRMS',
    )
    doc.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    buf.seek(0)
    return buf


# --------------------------------------------------------------------------
# SDSO — LIST OF SCHOLARS
# --------------------------------------------------------------------------

MASTERLIST_SIGNATORIES = [
    ('Prepared by:', 'MARICEL S. SAULAN', 'Scholarship in charge'),
    ('Noted:', 'NORMA M. DUALLO, Ph.D.TM', 'SDSO Director'),
    ('Recommending approval:', 'ERWIN G. SALVATIERRA, Ph. D.',
     'VP for Extension Services, Student and External Affairs'),
    ('Approved:', 'VICTOR C. CAÑEZO, JR., Ed. D.', 'University President'),
]


def masterlist_blocks():
    """One entry per programme, in the order the Word document prints them.

    Rows are resolved against each table's own headings, so a block's cells
    line up with its columns whatever shape that programme's table has.
    """
    from . import masterlist_report

    context, summary = masterlist_report.build_context()
    blocks = []
    for entry in summary:
        slot = context[entry['slot']]
        headers = entry['headers']

        def cells(rows):
            return [masterlist_report.cells_for(r, headers) for r in rows]

        if entry['layout'] == 'gendered':
            groups = [('FEMALE', cells(slot['female'])),
                      ('MALE', cells(slot['male']))]
        else:
            groups = [('', cells(slot['students']))]

        blocks.append({
            'heading': entry['heading'],
            'headers': headers,
            'groups': groups,
            'total': entry['total'],
        })
    return blocks, summary


def masterlist_pdf(academic_year, semester):
    """Return ``(BytesIO, summary)`` — the masterlist laid out as a page."""
    blocks, summary = masterlist_blocks()

    story = _letterhead(
        [
            ('Republic of the Philippines', SUBTITLE),
            ('BILIRAN PROVINCE STATE UNIVERSITY', TITLE),
            ('Naval, Biliran', SUBTITLE),
            (f'LIST OF SCHOLARS FOR {semester} SY: {academic_year}', PERIOD),
        ],
        legend='Legend:  @ - Internal    * - External',
    )

    for block in blocks:
        headers, groups = block['headers'], block['groups']
        if not headers:
            continue
        # One width set per programme, so its FEMALE and MALE tables line up
        # column for column instead of drifting apart on row content.
        widths = _column_widths(
            headers, [r for _label, rows in groups for r in rows])

        # Enough room for the heading and a line or two under it, or the whole
        # section starts on the next page rather than the heading being
        # stranded at the foot of this one.
        story.append(CondPageBreak(1.2 * inch))
        story.append(_banner(
            f'{block["heading"]} SCHOLARSHIP GRANT — {semester} SY: {academic_year}'))
        for label, rows in groups:
            if label:
                story.append(Paragraph(label, GROUP))
            story.append(_table(headers, rows, widths))
        story.append(Spacer(1, 12))

    story.append(CondPageBreak(1.4 * inch))
    story.extend(_signatories(MASTERLIST_SIGNATORIES))
    return _build(story, f'BiPSU List of Scholars {academic_year}'), summary


# --------------------------------------------------------------------------
# UniFAST — CHED Annex 2 Official List
# --------------------------------------------------------------------------

TES_SIGNATORIES = [
    ('Prepared by:', 'TES Focal Person / Scholarship Coordinator',
     '(Print Name and Signature)'),
    ('Certified by:', 'Registrar', '(Print Name and Signature)'),
    ('Approved by:', 'President', '(Print Name and Signature)'),
]

TES_INSTRUCTIONS = [
    'Identify the status of the student-grantee (make necessary corrections to '
    'the student personal details if needed).',
    'Complete all Annexes: Annex 2-Form 1, Annex 2-Form 2, and Annex 2-Form 4.',
    'Submit the documentary requirements to CHEDRO.',
]


def tes_official_list_pdf(academic_year, semester, batch=''):
    """Return ``(BytesIO, rows)`` — the CHED 'Official List' sheet as a page."""
    from . import tes_report

    rows = tes_report.grantee_rows(batch=batch)
    headers = tes_report.OFFICIAL_LIST_HEADERS
    values = [tes_report.row_values(r) for r in rows]

    story = _letterhead([
        ('LIST OF CONTINUING TES GRANTEES SUBJECT FOR VALIDATION', TITLE),
        ('BILIRAN PROVINCE STATE UNIVERSITY', SUBTITLE),
        (f'TES Batch {batch or "On-going"}, {semester}, AY {academic_year}',
         SUBTITLE),
    ])

    story.append(Paragraph('INSTRUCTIONS:', NOTE_HEAD))
    for i, line in enumerate(TES_INSTRUCTIONS, 1):
        story.append(Paragraph(f'{i}. {escape(line)}', NOTE))
    story.append(Spacer(1, 8))

    widths = _column_widths(headers, values)
    story.append(_table(headers, values, widths))

    if values:
        # Both amount columns print blank: CHED sets what each grantee is paid,
        # so the office enters those figures in the workbook itself.
        total = Table(
            [[Paragraph('TOTAL TERTIARY EDUCATION SUBSIDY', CELL_HEAD),
              Paragraph('to be entered by the office', CELL)]],
            colWidths=[sum(widths[:13]), sum(widths[13:])],
            hAlign='LEFT',
        )
        total.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HEADER_BG),
            ('GRID', (0, 0), (-1, -1), 0.4, GRID),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(total)

    story.append(CondPageBreak(1.4 * inch))
    story.extend(_signatories(TES_SIGNATORIES))
    return _build(story, f'TES Validation List {academic_year}'), rows
