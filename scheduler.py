# from apscheduler.schedulers.blocking import BlockingScheduler
from website.bots import bot_6010000, bot_6010001, bot_6010002, bot_6010003, bot_6010004, bot_6010005
from website import create_app

app = create_app()

def bot_601000x_wrapper(app):
    with app.app_context():
        # bot_6010000()
        # bot_6010001()
        bot_6010002()
        # bot_6010003()
        # bot_6010004()
        # bot_6010005()

bot_601000x_wrapper(app)

print("stop")