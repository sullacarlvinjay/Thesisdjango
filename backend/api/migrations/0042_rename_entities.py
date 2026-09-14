from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0041_correct_hardcoded_terms'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='archiverecord',
            name='api_archive_scholar_bcdf30_idx',
        ),

        migrations.RenameModel(
            old_name='ArchiveRecord',
            new_name='ImportedScholar',
        ),
        migrations.RenameModel(
            old_name='ScholarshipRollover',
            new_name='ScholarListImport',
        ),
        migrations.RenameModel(
            old_name='AffirmativeNSUApplication',
            new_name='AffirmativeStaffApplication',
        ),

        migrations.RenameField(
            model_name='importedscholar',
            old_name='year',
            new_name='year_level',
        ),
        migrations.RenameField(
            model_name='importedscholar',
            old_name='rollover_label',
            new_name='term_label',
        ),
        migrations.RenameField(
            model_name='scholarlistimport',
            old_name='label',
            new_name='term_label',
        ),
        migrations.RenameField(
            model_name='scholarlistimport',
            old_name='rolled_over_by',
            new_name='imported_by',
        ),
        migrations.RenameField(
            model_name='scholarshiplinkrequest',
            old_name='school_year',
            new_name='term_label',
        ),
    ]
