from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0002_application_edu_match_score_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='application',
            name='qualification_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending Evaluation'),
                    ('qualified', 'Qualified'),
                    ('under_qualified', 'Under Qualified'),
                    ('not_qualified', 'Not Qualified'),
                ],
                default='pending',
                max_length=30,
            ),
        ),
    ]