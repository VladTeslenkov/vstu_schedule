from asgiref.sync import sync_to_async
from timetable.models import Task
from timetable.task.clear_storage import task_clear
from timetable.task.snapshot import task_make_snapshot
from timetable.management.commands.update_timetable import Command
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def make_task(task: Task):
    action = task.params.get("action", None)
    logger.info(f"Starting task with action: {action}")
    match action:
        case "make_new":
            await task_make_snapshot(task)
        case "dell":
            await sync_to_async(task_clear)(task)
        case "update_timetable":
            try:
                logger.info("Starting timetable update")
                await sync_to_async(Command().update_timetable)()
                task.result = {"finished": str(datetime.now())}
                task.status = "success"
                logger.info("Timetable update completed successfully")
            except Exception as e:
                logger.error(f"Error during timetable update: {str(e)}", exc_info=True)
                task.status = "error"
                task.result = {"error": str(e)}
            await sync_to_async(task.save)()
