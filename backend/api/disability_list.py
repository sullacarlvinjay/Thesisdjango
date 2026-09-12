"""The Disability Type list the student record offers, read from CHED's workbook.

Disability is asked at registration and kept on
:class:`~api.models.PersonalInformation`, so it outlives the TES application
this list arrived with. The values are CHED's own — taken from the
``Disability_List`` sheet of the Annex 1 workbook the office keeps — rather than
a list retyped here, so a newer template drops in without a code change.

Only the sheet is read. Nothing is written back, and no report is produced from
it; the workbook is a reference list that happens to ship as a spreadsheet.
"""
import os

# The office's copy of CHED's form. Read for its lookup sheet, never written to.
TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates', 'xlsx', 'tes_annex1_applicants_template.xlsm',
)

SHEET = 'Disability_List'

# What a student picks when their case is not on CHED's list. Kept out of the
# sheet because it is this system's word, not CHED's — the value that gets
# stored is whatever they then type.
OTHER = 'Other'

_CACHE = {}


def disability_types():
    """The disability values the form offers, in the sheet's own order.

    'NO' leads it, which is how CHED's list spells 'not applicable' — a student
    choosing it is answering the question, not leaving it blank. ``OTHER`` is
    appended for a condition the list does not name; the student types that one
    out themselves.

    An empty list when the workbook is missing rather than an exception: the
    registration form has to render either way, and a student who cannot pick a
    disability is better served than one who cannot register.
    """
    if SHEET in _CACHE:
        return _CACHE[SHEET] + [OTHER]

    values = []
    if os.path.exists(TEMPLATE_PATH):
        import openpyxl
        wb = openpyxl.load_workbook(TEMPLATE_PATH, read_only=True, data_only=True)
        try:
            sheet = wb[SHEET]
            values = [str(cell.value).strip()
                      for (cell,) in sheet.iter_rows(min_row=2, max_col=1)
                      if cell.value is not None and str(cell.value).strip()]
        finally:
            wb.close()

    _CACHE[SHEET] = values
    return values + [OTHER]
