"""The disability options offered on the forms.

``NO`` is one of them on purpose — it is an answer, and the recommender must
tell declining apart from never having been asked.
"""

import os

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates', 'xlsx', 'tes_annex1_applicants_template.xlsm',
)

SHEET = 'Disability_List'

OTHER = 'Other'

_CACHE = {}


def disability_types():
    """The disability options offered on the forms.

    ``NO`` is one of them on purpose. It is an answer, and the recommender
    has to tell "declines to claim a disability" apart from "nobody asked".
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
