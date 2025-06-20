# Generated by Django 4.2.20 on 2025-06-14 06:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('problems', '0010_question_contribution_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='question',
            name='contribution_status',
            field=models.CharField(blank=True, choices=[('QUESTION_SUBMITTED', 'Question Submitted'), ('TEST_CASES_SUBMITTED', 'Test Cases Submitted'), ('CODE_SUBMITTED', 'Code Submitted'), ('COMPLETED', 'Completed')], default='QUESTION_SUBMITTED', max_length=20, null=True),
        ),
    ]
