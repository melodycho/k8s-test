import os
import re
import time
from datetime import datetime
def calTime(time0,time1):
    return datetime.strptime(time1,"%H:%M:%S")-datetime.strptime(time0,"%H:%M:%S")
def shell_exc(commands):
    stdout = os.popen(commands)
    lines = stdout.readlines()
    result = []
    print lines
    for line in lines:
        words = re.split("\s+",line)
        for word in words:
            if word:
                result.append(word)
    return result
print shell_exc("kubectl -s http://139.159.246.115:8080 get pod -o wide")
#stdoutTime = shell_exc("kubectl -s http://139.159.246.115:8080 describe pods nginx-72mbw")
#print stdoutTime
#print stdoutTime[stdoutTime.index('Start')+6]
#print stdoutTime[stdoutTime.index('Started:')+5]
#print calTime(stdoutTime[stdoutTime.index('Start')+6],stdoutTime[stdoutTime.index('Started:')+5])
