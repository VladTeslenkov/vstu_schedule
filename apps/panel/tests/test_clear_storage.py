import logging

import pytest

from apps.common.services.timetable_update.clear_storage import (
    TASK_LOGS_COMPONENT,
    clear_storage_by_component,
)
from apps.panel.models import CeleryTaskLog, CeleryTaskRun


@pytest.mark.django_db
def test_clear_task_logs_preserves_current_task_run():
    old_run = CeleryTaskRun.objects.create(
        task_id="old-task-id",
        task_name="panel.tasks.update_timetable",
    )
    current_run = CeleryTaskRun.objects.create(
        task_id="current-task-id",
        task_name="panel.tasks.clear_storage",
    )
    CeleryTaskLog.objects.create(
        run=old_run,
        level=logging.INFO,
        level_name="INFO",
        logger_name="test",
        message="old",
    )
    CeleryTaskLog.objects.create(
        run=current_run,
        level=logging.INFO,
        level_name="INFO",
        logger_name="test",
        message="current",
    )

    clear_storage_by_component(TASK_LOGS_COMPONENT, preserve_task_id=current_run.task_id)

    assert not CeleryTaskRun.objects.filter(task_id=old_run.task_id).exists()
    assert CeleryTaskRun.objects.filter(task_id=current_run.task_id).exists()
    assert list(CeleryTaskLog.objects.values_list("message", flat=True)) == ["current"]
