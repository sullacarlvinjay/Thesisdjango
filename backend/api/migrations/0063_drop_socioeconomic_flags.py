"""Drop the four socio-economic checkboxes the profile no longer asks about.

* ``is_pwd`` moved to ``PersonalInformation.disability_type`` in 0062, which
  says *which* disability rather than only that there is one.
* ``is_athlete`` and ``is_coconut_farmer_family`` were collected and then read
  by nothing that decides anything: the Sports and CoScho programmes are
  awarded off the office's own lists, not off a box a student ticks.
* ``has_other_scholarship`` said a student holds something else without saying
  what, which is a question the office could not act on. The registration form
  now asks for the scholarship itself — type, award number and proof — as a
  ``ScholarshipLinkRequest``, and the TES recommender reads that instead.

Nothing reads these columns after 0062, so dropping them loses no answer that
is still asked for.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0062_profile_disability_type'),
    ]

    operations = [
        migrations.RemoveField(model_name='socioeconomicprofile', name='is_pwd'),
        migrations.RemoveField(model_name='socioeconomicprofile', name='is_athlete'),
        migrations.RemoveField(model_name='socioeconomicprofile',
                               name='is_coconut_farmer_family'),
        migrations.RemoveField(model_name='socioeconomicprofile',
                               name='has_other_scholarship'),
    ]
