from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0082_renewal_says_which_programme'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='photo',
            field=models.ImageField(
                blank=True,
                help_text='Square headshot, any common image format.',
                null=True,
                upload_to='profile/photos/',
            ),
        ),
    ]
