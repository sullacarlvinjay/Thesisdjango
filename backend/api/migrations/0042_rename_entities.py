"""Rename three models and five fields, preserving every row.

Written by hand on purpose. Left to itself, ``makemigrations`` cannot tell a
rename from a delete-plus-create and, run non-interactively, picks the latter —
which would drop 115 imported scholars, 3 uploaded sheets and 2 affirmative
applications and recreate the tables empty. ``RenameModel`` and ``RenameField``
rename the table and the column in place instead, so the data simply moves with
the name.

    ArchiveRecord             -> ImportedScholar
      .year                   -> .year_level
      .rollover_label         -> .term_label
    ScholarshipRollover       -> ScholarListImport
      .label                  -> .term_label
      .rolled_over_by         -> .imported_by
    AffirmativeNSUApplication -> AffirmativeStaffApplication
    ScholarshipLinkRequest
      .school_year            -> .term_label

The composite index is dropped first and re-added afterwards by the migration
that follows: it names two of the columns being renamed, and an index cannot be
carried across a rename of its own fields.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0041_correct_hardcoded_terms'),
    ]

    operations = [
        # The index names rollover_label, so it goes before that column is renamed.
        migrations.RemoveIndex(
            model_name='archiverecord',
            name='api_archive_scholar_bcdf30_idx',
        ),

        # ── models ──────────────────────────────────────────────────────────
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

        # ── fields, addressed by the new model names ────────────────────────
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
