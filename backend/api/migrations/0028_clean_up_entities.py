from django.db import migrations


class Migration(migrations.Migration):
    """Entity cleanup: one name per concept, and drop what nothing uses.

    - The student's BiPSU ID number was spelled three ways. StudentProfile
      already called it ``student_id``; ArchiveRecord and
      AffirmativeNSUApplication now match. ``staff_employee_id`` is left alone —
      it identifies the *sponsoring* staff member of a dependent, not the
      applicant, so it is genuinely a different thing.
    - ``scholar_name`` was a denormalised copy of first + last name that was
      written on import but never read; ``extra_data`` was never referenced.
    - ``Renewal`` and ``TDPApplication`` were superseded by AcademicRenewal /
      StaffRenewal and by Application rows of type TDP. Nothing ever created a
      row in either, so both tables are empty.
    """

    dependencies = [
        ('api', '0027_add_award_number_to_tesapplication'),
    ]

    operations = [
        migrations.RenameField(
            model_name='archiverecord',
            old_name='student_number',
            new_name='student_id',
        ),
        migrations.RenameField(
            model_name='affirmativensuapplication',
            old_name='school_id',
            new_name='student_id',
        ),
        migrations.RemoveField(model_name='archiverecord', name='scholar_name'),
        migrations.RemoveField(model_name='archiverecord', name='extra_data'),
        migrations.DeleteModel(name='Renewal'),
        migrations.DeleteModel(name='TDPApplication'),
    ]
