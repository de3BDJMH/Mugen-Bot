import pytz,datetime
today=datetime.datetime.now()
start=(today-datetime.timedelta(0)).timestamp()
timezone = pytz.timezone('Asia/Shanghai')
savetime=datetime.datetime.fromtimestamp(start,timezone)
print(f"{savetime.year}_{savetime.month}_{savetime.day}")