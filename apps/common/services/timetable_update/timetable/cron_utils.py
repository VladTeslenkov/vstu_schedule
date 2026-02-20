import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings
from timetable.models import Setting

logger = logging.getLogger(__name__)

scheduler = None


def init_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")
        try:
            scheduler.start()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}", exc_info=True)
            raise


def schedule_update_timetable():
    from timetable.management.commands.update_timetable import Command

    try:
        Command.update_timetable()
        logger.info("Timetable update task executed successfully")
    except Exception as e:
        logger.error(f"Error executing timetable update: {str(e)}", exc_info=True)


def configure_update_task():
    try:
        # Получаем интервал из настроек
        minutes = int(Setting.objects.get(key="time_update").value)
    except (Setting.DoesNotExist, ValueError, TypeError):
        minutes = 180  # Значение по умолчанию
        logger.warning("Using default timetable update interval: 180 minutes")

    global scheduler
    if scheduler is None:
        init_scheduler()

    # Удаляем существующую задачу, если она есть
    try:
        scheduler.remove_job("update_timetable")
        logger.info("Existing timetable update task removed")
    except:
        pass

    # Добавляем новую задачу с указанным интервалом
    scheduler.add_job(
        schedule_update_timetable,
        trigger=IntervalTrigger(minutes=minutes),
        id="update_timetable",
        max_instances=1,
        replace_existing=True,
    )
    logger.info(f"Scheduled timetable update every {minutes} minutes")


def create_update_timetable_cron_task():
    init_scheduler()
    configure_update_task()
