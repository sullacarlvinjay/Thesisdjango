from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0086_declaration_filed_in_portal'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='terms_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='terms_version',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
