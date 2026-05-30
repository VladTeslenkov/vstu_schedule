from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0004_merge_0002_alter_department_name_0003_file_version_and_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fileversion",
            name="hashsum",
            field=models.CharField(
                max_length=255,
                verbose_name="Контрольная сумма содержимого файла",
            ),
        ),
    ]
