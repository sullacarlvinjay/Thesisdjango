from django.db import migrations


class Migration(migrations.Migration):
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
