from apscheduler.schedulers.blocking import BlockingScheduler
from website.bots import bot_6010000
from website import create_app
import time

def bot_6010000_wrapper(app):
    with app.app_context():
        bot_6010000()

app = create_app()
# scheduler = BlockingScheduler()
# scheduler.add_job(bot_6010000_wrapper, "interval", minutes = 5)

if __name__ == "__main__":
    print("Beginning the loop for bot 6010000")
    # with website.app_context():
    # scheduler.start()
    while True:
        bot_6010000_wrapper(app)
        time.sleep(300)