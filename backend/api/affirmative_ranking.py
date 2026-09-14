from dataclasses import dataclass

from .tes_ranking import _stated

INDIGENOUS = 'Indigenous group'
PWD = 'Person with a disability'
PUBLIC_SCHOOL = 'Public school'
DEPRESSED_AREA = 'Depressed area'


@dataclass(frozen=True)
class TargetGroups:
    markers: tuple = ()
    unknown: tuple = ()

    @property
    def count(self):
        return len(self.markers)

    @property
    def summary(self):
        return ' · '.join(self.markers)


def target_groups(profile):
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
