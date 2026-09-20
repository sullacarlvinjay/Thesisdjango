"""Affirmative Action target groups.

The four groups come from the PASUC-8 proposal: indigenous community, person
with a disability, public high school, depressed area.

Membership and unanswered questions are kept apart. "Not in this group" and
"nobody has answered yet" would rank identically if merged, and only one of
them is a fact about the applicant.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .tes_ranking import _stated

if TYPE_CHECKING:
    from .models import StudentProfile

INDIGENOUS = 'Indigenous group'
PWD = 'Person with a disability'
PUBLIC_SCHOOL = 'Public school'
DEPRESSED_AREA = 'Depressed area'


@dataclass(frozen=True)
class TargetGroups:
    """Which Affirmative Action target groups an applicant falls into.

    Markers and unknowns are kept apart on purpose. "Not in this group" and
    "nobody has answered yet" would rank the same if they were merged, and
    only one of them is a fact about the applicant.
    """
    markers: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        """How many target groups the applicant is in."""
        return len(self.markers)

    @property
    def summary(self) -> str:
        """The markers as one readable line."""
        return ' · '.join(self.markers)


def target_groups(profile: 'StudentProfile') -> TargetGroups:
    """Read an applicant's target-group membership off their profile.

    The four groups come from the PASUC-8 proposal: indigenous community,
    person with a disability, public high school, depressed area.

    An unanswered question is recorded as unknown rather than as a "no". The
    distinction decides whether the office chases the applicant for an answer
    or rules on what it has, and collapsing the two would quietly downgrade
    everyone whose form was incomplete.

    Returns:
        A :class:`TargetGroups` carrying the markers earned and the questions
        still outstanding.
    """
    markers, unknown = [], []

    group = _stated(profile.indigenous_group)
    if group:
        markers.append(f'{INDIGENOUS} ({group})')

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
