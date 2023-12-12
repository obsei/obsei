from crontab import CronTab

cron = CronTab(user='namtong')
job = cron.new(command='streamlit hello')
job.minute.every(1)
cron.write()
