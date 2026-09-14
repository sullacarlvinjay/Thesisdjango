from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0029_entity_choice_lists'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='middle_name',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
