from django.db import migrations


ALERT_TITLE = "Расписание может измениться"
ALERT_BODY = "Актуальную информацию уточняйте на официальном сайте университета."
ALERT_TITLE_EN = "Schedule may change"
ALERT_BODY_EN = "Please check the official university website for the most up-to-date information"


def create_schedule_accuracy_alert(apps, schema_editor):
    alert_model = apps.get_model("common", "Alert")
    alert_model.objects.update_or_create(
        title=ALERT_TITLE,
        body=ALERT_BODY,
        defaults={
            "category": "warning",
            "is_enabled": True,
            "is_admin": False,
            "is_dismissible": False,
            "title_en": "",
            "body_en": "",
            "starts_at": None,
            "expires_at": None,
        },
    )


def delete_schedule_accuracy_alert(apps, schema_editor):
    alert_model = apps.get_model("common", "Alert")
    alert_model.objects.filter(
        title=ALERT_TITLE,
        body=ALERT_BODY,
        category="warning",
        is_dismissible=False,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0009_indexes"),
    ]

    operations = [
        migrations.RunPython(create_schedule_accuracy_alert, delete_schedule_accuracy_alert),
    ]
