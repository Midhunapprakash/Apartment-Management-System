from apscheduler.schedulers.background import BackgroundScheduler
from .tasks import expire_old_bookings

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(expire_old_bookings, 'interval', minutes=5)
    scheduler.start()