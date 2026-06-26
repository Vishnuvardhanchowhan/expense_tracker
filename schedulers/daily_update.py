import schedule
import time
from datetime import date
from src.build_master import build_master


def daily_task():
    print(f"Running daily update at {date.today()}")
    build_master()  # Your function


schedule.every().day.at("09:00").do(daily_task)  # 9 AM IST

while True:
    schedule.run_pending()
    time.sleep(60)