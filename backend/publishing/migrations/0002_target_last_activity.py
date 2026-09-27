from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publishing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicationtarget',
            name='last_activity_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
