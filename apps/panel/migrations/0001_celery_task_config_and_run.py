import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="CeleryTaskConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_name", models.CharField(max_length=255, unique=True)),
                ("enabled", models.BooleanField(default=False)),
                ("cron_minute", models.CharField(default="0", max_length=64)),
                ("cron_hour", models.CharField(default="*", max_length=64)),
                ("cron_day_of_week", models.CharField(default="*", max_length=64)),
                ("cron_day_of_month", models.CharField(default="*", max_length=64)),
                ("cron_month_of_year", models.CharField(default="*", max_length=64)),
                ("soft_time_limit_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("time_limit_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "periodic_task",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="panel_task_config",
                        to="django_celery_beat.periodictask",
                    ),
                ),
            ],
            options={
                "db_table": "panel_celery_task_config",
                "ordering": ["task_name"],
            },
        ),
        migrations.CreateModel(
            name="CeleryTaskRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_id", models.CharField(max_length=255, unique=True)),
                ("task_name", models.CharField(db_index=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("STARTED", "Started"),
                            ("SUCCESS", "Success"),
                            ("FAILURE", "Failure"),
                            ("RETRY", "Retry"),
                            ("REVOKED", "Revoked"),
                            ("SKIPPED", "Skipped"),
                        ],
                        default="PENDING",
                        max_length=32,
                    ),
                ),
                ("queued_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("result_text", models.TextField(blank=True, default="")),
                ("traceback_text", models.TextField(blank=True, default="")),
            ],
            options={
                "db_table": "panel_celery_task_run",
                "ordering": ["-queued_at"],
            },
        ),
    ]
