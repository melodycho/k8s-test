#-*- coding: utf-8 -*-
#!/usr/bin/python
import paramiko
import threading
import re
import os
import sqlite3
import time
from datetime import datetime
import unittest
import logging
import logging.config
import ConfigParser
import chardet
#from pyh import *
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

NODEIP = "162.3.210.32"
MASTERIP = "139.159.246.115"
ETHNAME = "eno16777984"
cx = sqlite3.connect('test0810.db')
cu = cx.cursor()

def createlog(name=__name__,log_file_name = 'test.log',debug=[],info=[],warn= [],error= [],fetal=[]):
    try:
        if os.path.getsize(log_file_name) > 1000000:
            os.remove(log_file_name)
    except BaseException:
        print 'txt can not be deleted'
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        # create a file handler
        handler = logging.FileHandler(log_file_name)
        handler.setLevel(logging.DEBUG)
        # create a logging format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        handler.setFormatter(formatter)
        # add the handlers to the logger
        logger.addHandler(handler)
        ########################解决日志重复的问题logger.removeHandler(handler)
    if info:logger.info(info)
    if debug:logger.debug(debug)
    if warn:logger.warning(warn)
    if error:logger.error(error)
    if fetal:logger.fatal(fetal)

def deleteDB(DBtable):
    #######删除数据库表格
    cu.execute('drop table if exists '+ DBtable+';')
    createlog(name='__dbconnect__',warn=['Warning##drop a database Table :',DBtable])
def createDB(DBtable,*dbinfo):
    #######创建数据库结果表格
    print dbinfo
    temp = str(dbinfo)
    try:
        cu.execute('Create table if not exists '+ DBtable+' '+temp+';')
    except sqlite3.OperationalError as errorMessage:
        createlog(name='__createDB__',error=[errorMessage])
        createlog(name='__createDB__', info=['create a DB successfully: ',DBtable])
def insertResult(DBtable,info):
    try:
        now = time.strftime("%Y-%m-%d-%H:%M:%S")
        info.append(now)
        n = len(info)-1
        dbinfo = '('+'?'+ ',?'*n + ')'
        cmd1 = "INSERT into %s VALUES %s" % (DBtable,dbinfo)
        #########################windows系统下,如果不是读取文件，则注释掉以下两句################################################
        #print chardet.detect(info[0])['encoding']
        #print type(info[0])
        if isinstance(info[0],str):
            info[0] = info[0].decode('gbk')
            info[1] = info[1].decode('gbk')
        cu.execute(cmd1,info)
        print 'DB info 中文 : ',info
        cx.commit()
        #cx.close()
    except Exception as error_Message:
        createlog(name= '__insertResult__',error=['databaseError',error_Message])

def calTime(time0,time1):
    return str(datetime.strptime(time1,"%H:%M:%S")-datetime.strptime(time0,"%H:%M:%S"))


def shell_exc(commands):
    stdout = os.popen(commands)
    lines = stdout.readlines()
    result = []
    for line in lines:
        words = re.split('\s+',line)
        for word in words:
            if word:result.append(word)
    return result

def set_nodeStatus(masterIP):
    stdout = shell_exc("kubectl -s http://"+masterIP+":8080 get node")
    deleteDB("NodeStatus")
    createDB("NodeStatus",'NAME TEXT','STATUS','AGE','VERSION','sysTime')
    for i in xrange(len(stdout)/4):
        print stdout[4*(i+1):4*(i+2)]
        insertResult("NodeStatus",stdout[4*(i+1):4*(i+2)])

def checkPodStatus(podStatus="Running"):
    set_podStatus(MASTERIP)
    cu.execute("select STATUS from podStatus")
    for file in cu.fetchall():
        print file
        if file[0]!=podStatus:return file[0]
    return podStatus

def createPod(masterIP,podNum=1,rcName='nginx'):
    shell_exc("kubectl -s http://"+masterIP+":8080 "+"scale rc "+rcName+" --replicas=0")
    checkInfo = shell_exc("kubectl -s http://"+masterIP+":8080 get pod -o wide")
    while checkInfo:
        checkInfo = shell_exc("kubectl -s http://"+masterIP+":8080 get pod -o wide")
        print checkInfo
        time.sleep(2)
    shell_exc("kubectl -s http://"+masterIP+":8080 "+"scale rc "+rcName+" --replicas="+str(podNum))
    podStatus = checkPodStatus()
    print podStatus
    count = 100
    while podStatus!="Running" and count:
        allpodStatus = checkPodStatus()
        print allpodStatus
        count -= 1
    return "All Pods Running..."

def set_podStatus(masterIP):
    op0 = "kubectl -s http://"+masterIP+":8080 get pod -o wide"
    stdout = shell_exc(op0)
    deleteDB("podStatus")
    createDB("podStatus",'NAME TEXT','READY','STATUS',"RESTARTS",'AGE','IP','NODE','Start Time','Started','CreatePodTime','sysTime')
    CreatePodTime = []
    for i in xrange(len(stdout)/7-1):
        print stdout[7*(i+1):7*(i+2)],
        podStatusInfo = stdout[7*(i+1):7*(i+2)]
        print podStatusInfo
        if podStatusInfo[2]=='Running':
            stdoutTime = shell_exc("kubectl -s http://"+masterIP+":8080 describe pods "+podStatusInfo[0])
            podStartTime = stdoutTime[stdoutTime.index('Start')+6]
            podStartedTime = stdoutTime[stdoutTime.index('Started:')+5]
            podStatusInfo.append(podStartTime)
            podStatusInfo.append(podStartedTime)
            podStatusInfo.append(calTime(podStartTime,podStartedTime))
            print podStatusInfo
            CreatePodTime.append(podStatusInfo[-1])
        else:
            for i in xrange(3):podStatusInfo.append(' ')
        insertResult("podStatus",podStatusInfo)
    return CreatePodTime


def get_nodeStatus(masterIP,nodeIP):
    stdout = shell_exc("kubectl -s http://"+masterIP+":8080 get node")
    nodeIP_index = stdout.index(nodeIP)
    return stdout[nodeIP_index+1]



def tc_control(eth_name,args):
    print "Network reset..."
    op0 = "tc qdisc del dev "+eth_name+" root netem"
    os.system(op0)
    print "Delete network stings..."
    op1 = "tc qdisc add dev "+eth_name+" root netem "+args
    print 'Seting network...'
    os.system(op1)
    print 'Vertifing network Status...'
    output = os.popen("ping -c 10 "+MASTERIP).readlines()[-2:]
    for line in output:
        print line.strip('\n')
    return output

def ssh2(ip='162.3.210.32',username='root',passwd='huawei',commands=[]):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, 22, username, password=passwd, timeout=4)
    for cmd in commands:
        print cmd
        stdin, stdout, stderr = client.exec_command(cmd)
        for std in stdout.readlines():
          print std,
    print "%s\tOK\n"%ip
    client.close()

def testK8sNetwork(func1='delay',func2="200ms",podNum=1):
    timeInfo = [func2]
    print "Begin......"
    tc_control(ETHNAME,func1+' '+func2)
    nodeStatus = get_nodeStatus(masterIP=MASTERIP,nodeIP=NODEIP)
    shell_exc("systemctl start kubelet")
    shell_exc("systemctl stop kubelet")
    startTime = time.time()
    while nodeStatus=="Ready":
        #print "%s\t%s"%(NODEIP,nodeStatus)
        nodeStatus = get_nodeStatus(masterIP=MASTERIP,nodeIP=NODEIP)
    endTime = time.time()
    durTime = round(endTime-startTime,2)
    shell_exc("systemctl start kubelet")
    while nodeStatus=="NotReady":
        #print "%s\t%s"%(NODEIP,nodeStatus)
        nodeStatus = get_nodeStatus(masterIP=MASTERIP,nodeIP=NODEIP)
    durTime1 = round(time.time()-endTime,2)
    timeInfo.append(str(durTime))
    timeInfo.append(str(durTime1))
    createPod(MASTERIP,podNum=podNum,rcName="nginx")
    allPodLostTime = set_podStatus(MASTERIP)
    print allPodLostTime
    if allPodLostTime:
        totalTime = reduce(lambda x,y:x+y,map(lambda x:datetime.strptime(x,"%H:%M:%S")-datetime.strptime("0:0:0","%H:%M:%S"),allPodLostTime))
        avgTime = (datetime.strptime(str(totalTime),"%H:%M:%S")-datetime.strptime("0:0:0","%H:%M:%S"))/podNum
        timeInfo.append(str(avgTime))
    else:
       timeInfo.append('CreatePodFailed')
    print timeInfo
    return timeInfo

if __name__=='__main__':
    cmd = ['kubectl -s http://139.159.246.115:8080 get node -o wide','ls -l']
    #username = "root"
    #passwd = "Huawei@CLOUD8!"
    username = "root"
    passwd = "huawei"
    nodeIP = "162.3.210.32"
    threads = []
    #################test delay
    createDB("netDelay",'delayTime(ms)','ReadyToNotReady(s)','NotReadyToReady(s)','CreatePodTime','sysTime')
    for i in xrange(50,1500,50):
        timeInfo = testK8sNetwork(func1='delay',func2=str(i)+'ms')
        insertResult("netDelay",timeInfo)
    #################################################
    createDB("netLoss",'delayTime(ms)','ReadyToNotReady(s)','NotReadyToReady(s)','CreatePodTime','sysTime')
    for i in xrange(0,50,5):
        timeInfo = testK8sNetwork(func1='loss',func2=str(i)+'%')
        insertResult("netLoss",timeInfo)
        #################################################
    createDB("netCorrupt",'delayTime(ms)','ReadyToNotReady(s)','NotReadyToReady(s)','CreatePodTime','sysTime')
    for i in xrange(0,50,5):
        timeInfo = testK8sNetwork(func1='corrupt',func2=str(i)+'%')
        insertResult("netCorrupt",timeInfo)
            #################################################
    createDB("netDuplicate",'delayTime(ms)','ReadyToNotReady(s)','NotReadyToReady(s)','CreatePodTime','sysTime')
    for i in xrange(0,50,5):
        timeInfo = testK8sNetwork(func1='duplicate',func2=str(i)+'%')
        insertResult("netDuplicate",timeInfo)


    set_nodeStatus(MASTERIP)
    set_podStatus(MASTERIP)
    #ssh2(ip=nodeIP,username='root',passwd='huawei',commands=cmd)
    #ssh2(ip,username,passwd,cmd)
    #a=threading.Thread(target=ssh2,args=(ip,username,passwd,cmd))
    #a.start()
