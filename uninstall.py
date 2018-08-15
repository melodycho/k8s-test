#-*-coding=UTF-8-*-
#!/usr/bin/env python
import subprocess
import pexpect
import json
import getpass, os
import traceback
from deploy_log import LOGING


log_ = LOGING(log_file_name="./log/pre_paas_install.log")

class Node(object):
    def __init__(self, node_ip, pwd):
        self.node_ip = node_ip
        self.pwd = pwd

    def ssh_command(self, user, command):
        ssh_newkey = 'Are you sure you want to continue connecting'
        child = pexpect.spawn('ssh -l %s %s %s' % (user, self.node_ip, command))
        i = child.expect([pexpect.TIMEOUT, ssh_newkey, 'password: '])
        if i == 0:  # Timeout
            log_.error( 'ERROR!')
            log_.error('SSH could not login. Here is what SSH said:')
            log_.info(str(child.before)+str(child.after))
            return None
        if i == 1:  # SSH does not have the public key. Just accept it.
            child.sendline('yes')
            child.expect('password: ')
            i = child.expect([pexpect.TIMEOUT, 'password: '])
            if i == 0:  # Timeout
                log_.error('ERROR!')
                log_.error('SSH could not login. Here is what SSH said:')
                log_.info(str(child.before) + str(child.after))
            return None
        child.sendline(self.pwd)
        log_.info(("ssh command : %s"%(command)))
        return child

    def scp_command(self, src_file, des_file):
        ssh_newkey = 'Are you sure you want to continue connecting'
        log_.info('scp %s paas@%s:%s' % (src_file, self.node_ip, des_file))
        child = pexpect.spawn('scp %s root@%s:%s' % (src_file, self.node_ip, des_file))
        i = child.expect([pexpect.TIMEOUT, ssh_newkey, 'password: '])
        if i == 0:  # Timeout
            log_.error('ERROR!')
            log_.error('SSH could not login. Here is what SSH said:')
            log_.info(str(child.before) + str(child.after))
            return None
        if i == 1:  # SSH does not have the public key. Just accept it.
            child.sendline('yes')
            child.expect('password: ')
            i = child.expect([pexpect.TIMEOUT, 'password: '])
            if i == 0:  # Timeout
                log_.error('ERROR!')
                log_.error('SSH could not login. Here is what SSH said:')
                log_.info(str(child.before) + str(child.after))
            return None
        child.sendline(self.pwd)
        child.expect(pexpect.EOF)
        output = child.before.strip()
        log_.info("scp : %s, ret : %s"%(src_file, output))
        return output

    def change_paas_env(self):
        output = ""
        child = self.ssh_command("root", "cat /etc/shadow | grep paas")
        child.expect(pexpect.EOF)
        output = child.before
        log_.info(("user paas shadow : %s"%(output)))
        if not output.strip():
            commands = ['echo "paas:x:1000:1000::/home/paas:/bin/bash" >> /etc/passwd',
                        'echo "wheel:x:10:paas\ndocker:x:1001:paas\npaas:x:1000:" >> /etc/passwd',
                         'echo "paas:$6$sMKvlYyx$hKQ7zF0RXC8t/ip60h/sBpqlrCJ1ZQRjpkFCGmB7PJjUir7yM115O0CEeHZh4aWu3aBlY1CRrROo.7wPJs.gx0:17289:0:999999:7:99999::" >> /etc/shadow']
            for command in commands:
                child = self.ssh_command("root", command)
                child.expect(pexpect.EOF)
                output = child.before
                log_.info(("Change user paas : %s, %s"%(command, output)))
        child = self.ssh_command("root", "cat /proc/cmdline | grep ipv6.disable")
        child.expect(pexpect.EOF)
        output = child.before
        log_.info(("Check ipv6.disable : %s "%(output)))
        if "ipv6.disable=1" in output.strip():
            self.ssh_command("root", 'sed -i "s/ipv6.disable=1//g" /boot/grub2/grub.cfg')
            self.ssh_command("root", 'reboot')

    def exec_cmd(self, command):
        child = self.ssh_command("root", command)
        child.expect(pexpect.EOF)
        ret = child.before
        if ret:
            return ret.strip()
        return None

    def change_host_name(self, name = ""):
        commands = ["echo "+name+" > /etc/hostname", "echo "+name+" > /etc/HOSTNAME", "echo '127.0.0.1' "+name+" >> /etc/hosts", "hostname "+name, "hostname"]
        for command in commands:
            self.exec_cmd(command)

    def check_hostname(self, hostname=""):
        commands = ["echo $hostname", "echo $HOSTNAME"]
        for command in commands:
            if self.exec_cmd(command) == hostname:
                return True
        return False

    def check_docker_info(self):
        command = ["docker info"]
        output = ""
        for cmd in command:
            output = self.exec_cmd(cmd)
        if "docker: command not found" in output:
            return False
        return True

    def install_docker(self):
        command = ["sh /tmp/docker/install_docker.sh", "docker version"]
        output = ""
        for cmd in command:
            output = self.exec_cmd(cmd)
        if "docker: command not found" in output:
            return False
        return True

    def check_ssh_use_dns(self):
        command = ['sed -n "/UseDNS/"p /etc/ssh/sshd_config']
        for cmd in command:
            output = self.exec_cmd(cmd)
            if "UseDNS no" in output.strip():
                return False
        return True

    def change_ssh_config(self):
        command = ['sed -i "s/#UseDNS yes/UseDNS no/1"  /etc/ssh/sshd_config', "sudo systemctl restart sshd"]
        for cmd in command:
            output = self.exec_cmd(cmd)
            log_.info(("Change ssh config : %s"%(output)))

    def uninstall_node(self):
        child = self.scp_command(src_file="base_agent.sh", des_file="/tmp/")
        child = self.scp_command(src_file="uninstall_node.py", des_file="/tmp/")
        command = ["python /tmp/uninstall_node.py", "rm -f /tmp/base_agent.sh"]
        for cmd in command:
            output = self.exec_cmd(cmd)
            print "Uninstall node : ", output
            log_.info(("Uninstall Node : %s"%(output)))

    def create_log_file(self):
        child = self.scp_command(src_file="create_log_file_for_ief.sh", des_file="/tmp/")
        command = ["sh -x /tmp/create_log_file_for_ief.sh"]
        for cmd in command:
            output = self.exec_cmd(cmd)
            log_.info(("create_log_file : %s"%(output)))

def trav_ip():
    fp = open("node.json")
    nodes = json.load(fp)
    for node in nodes:
        try:
            log_.info(180 * "*")
            hostname = node["hostname"]
            node = Node(node_ip=node["ip"], pwd=node["password"])
            if node.check_ssh_use_dns():
                node.change_ssh_config()
            if not node.check_docker_info():
                child = node.scp_command(src_file="-r /tmp/qwq/docker/", des_file="/tmp/")
                node.install_docker()
            if not node.check_hostname(hostname):
                node.change_host_name(hostname)
            node.change_paas_env()
            node.uninstall_node()
            node.create_log_file()
        except Exception, e:
            log_.fetal(str(e))

if __name__ == '__main__':
    try:
        trav_ip()
    except Exception, e:
        log_.fetal(str(e))
        traceback.print_exc()
