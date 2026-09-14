from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0051_drop_moved_studentprofile_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='affirmativestaffapplication',
            name='extra_data',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='importedscholar',
            name='extra_data',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='scholarship',
            name='extra_columns',
            field=models.JSONField(blank=True, default=list, help_text="Columns the office added, as [{'key', 'label'}]."),
        ),
        migrations.AddField(
            model_name='scholarship',
            name='table_columns',
            field=models.JSONField(blank=True, default=list, help_text='Column keys from api/scholar_columns.COLUMNS. Empty means the default set.'),
        ),
    ]
