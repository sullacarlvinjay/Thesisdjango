"""Who the Affirmative Action programme is *for*, read off one student record.

The three criteria in section 2 of the PASUC-8 proposal — an SHS GPA of 75%, at
least 50% in the SUC-administered admission exam, and not being a TES
beneficiary — decide who *may* be put forward, and
:meth:`AffirmativeRecommendation.evaluate_and_sync` tests exactly those three.
They say nothing about who the programme is for. That is the mandate paragraph,
which names four groups:

    1. coming from the indigenous groups;
    2. person with disabilities;
    3. students from public schools; and
    4. students from depressed areas

This module reads those four off the student's own record.

**Nothing here is a gate.** Section 1 of the proposal is explicit that "the
grades will not be the only factor to qualify" and that qualifiers "may not
necessarily be indigent nor excellent academic performers" and "may be outside
the 4Ps of the DSWD". Belonging to none of the four disqualifies nobody, and an
unanswered question is never read as "no" — it is reported as unanswered, the
way :mod:`api.tes_ranking` reports a rule it could not run.

What the groups change is the **order of the shortlist**. Until now the
Affirmative tab ordered candidates by a fit score of 50% SHS GPA + 50% admission
exam, so an affirmative action programme handed the Board of Regents a merit
list — the one thing section 1 says it is not. The groups a student belongs to
now come first, and the score only separates students the mandate reaches
equally.

Field mapping (group -> the field actually read):

    Indigenous group    StudentProfile.indigenous_group        (SocioEconomicProfile)
    Disability          StudentProfile.disability_type         (PersonalInformation)
    Public school       StudentProfile.highschool_is_public    (EducationalBackground)
    Depressed area      StudentProfile.is_from_depressed_area  (SocioEconomicProfile)

The first two were already on every student record — collected for TES, which
reads them as priority markers — and were simply invisible to this programme.
The last two were added for it, because neither could be derived: no reading of
a school's *name* tells you whether it is public, and the proposal never defines
"depressed area" at all. Both are declared by the student for the office to
verify, which is how this system already handles Listahanan and 4Ps.

Like :mod:`api.tes_ranking` and :mod:`api.staff_ranking`, nothing here writes to
the database.
"""
from dataclasses import dataclass

# Borrowed rather than re-spelled: real records in this system hold 'N/A' in the
# free-text group fields, and a third copy of the set that knows 'N/A' means no
# is a third place for it to fall out of step.
from .tes_ranking import _stated

INDIGENOUS = 'Indigenous group'
PWD = 'Person with a disability'
PUBLIC_SCHOOL = 'Public school'
DEPRESSED_AREA = 'Depressed area'


@dataclass(frozen=True)
class TargetGroups:
    """The mandate groups one student is in, and the ones nobody has asked about."""
    markers: tuple = ()
    unknown: tuple = ()

    @property
    def count(self):
        return len(self.markers)

    @property
    def summary(self):
        """The groups as a single cell, for a table column or a workbook."""
        return ' · '.join(self.markers)


def target_groups(profile):
    """Which of the four groups this student belongs to.

    Read as a set rather than one question at a time: the four *are* the
    mandate, and a caller that wanted three of them would be asking something
    the proposal does not ask.

    An answer is only ever counted on positive evidence. Where the record is
    silent the group is not claimed — and, where silence is distinguishable
    from a "no", the question is named in ``unknown`` so the office can go and
    ask it rather than the student quietly losing a place they may be entitled
    to.
    """
    markers, unknown = [], []

    # Free text, and optional on every form that asks it, so blank is how a
    # student says no. There is no third state here to chase — unlike the two
    # below, where the form offers an explicit Yes and No.
    group = _stated(profile.indigenous_group)
    if group:
        markers.append(f'{INDIGENOUS} ({group})')

    # 'NO' is how CHED's own Disability_List declines the question, and _stated
    # reads it as a no. Blank is different: it means nobody asked, which is only
    # true of records taken before the question became required.
    disability = _stated(profile.disability_type)
    if disability:
        markers.append(f'{PWD} ({disability})')
    elif not (profile.disability_type or '').strip():
        unknown.append('Disability (or NO for none)')

    if profile.highschool_is_public is True:
        markers.append(PUBLIC_SCHOOL)
    elif profile.highschool_is_public is None:
        unknown.append('Whether the high school attended was public')

    if profile.is_from_depressed_area is True:
        markers.append(DEPRESSED_AREA)
    elif profile.is_from_depressed_area is None:
        unknown.append('Whether the student is from a depressed area')

    return TargetGroups(markers=tuple(markers), unknown=tuple(unknown))
