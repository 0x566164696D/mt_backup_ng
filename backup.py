#!/usr/bin/python
import os
import sys 
#import subprocess
import smtplib
import re
import socket
import difflib
import datetime
from multiprocessing.dummy import Pool as ThreadPool
from time import localtime
from time import strftime 
from time import sleep 
from distutils.version import LooseVersion
try:
    import paramiko
except ImportError:
    print("""
#########################################################
paramiko module not found. Please install it.
pip install paramiko
or
apt-get install python-paramiko
#########################################################""")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("""
#########################################################
yaml module not found. Please install it.
apt-get install python-yaml
or
pip install pyyaml
#########################################################""")
    sys.exit(1)

class Router():
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.timestamp = strftime("%d-%m-%Y (%H-%M)", localtime())
        self.start_time=datetime.datetime.now()
        self.ssh_client = paramiko.SSHClient()
        self.diff_report = ""
        self.error = ""
        self.duration = ""
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.verbose = True
    
    def getIPAndPort(self):
        return self.ip + ":" + self.port

    def getError(self):
        return self.error

    def getDiffInfo(self):
        return self.diff_report

    def ssh_connect(self):
        try:
            if config['auth_method'] == "key": 
                self.ssh_client.connect(hostname = self.ip, port = int(self.port), timeout = 3,
                                        username=config['Login'],pkey = config['pkey'])
            else:
                self.ssh_client.connect(hostname = self.ip, port = int(self.port), timeout = 3,
                                        look_for_keys = False, allow_agent = False,
                                        username = config['Login'], password = config['Password'])
            return True
        except paramiko.AuthenticationException:
            self.error = "Can't connect to {0}:{1}, Authentication failed \n".format(self.ip, self.port)
        except paramiko.SSHException:
            self.error = "Can't connect to {0}:{1}, SSHException. Maybe key auth failed\n".format(self.ip, self.port)
        except Exception as err:
            self.error = "Can't connect to {0}:{1}, {2}\n".format(self.ip, self.port, err)
        return False 

    def ssh_cmd(self, cmd):
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=10)
            self.ssh_get_data = stdout.read()
            return self.ssh_get_data.decode('utf-8')
        except Exception as err:
            self.error = "Can't send command to router {0}:{1} - {2}\n".format(self.ip, self.port, err)
            if self.verbose: print(self.error[:-1])
            self.ssh_client.close()
            return ""

    def ssh_get_file(self, remote_file, local_file):
        try:
            self.sftp = self.ssh_client.open_sftp()
            self.sftp.get(remote_file, local_file)
            self.sftp.close()
        except Exception as err:
            self.error = "Error: Can't get file from router {0}:{1} - {2}\n".format(self.ip, self.port, err)
            if self.verbose: print(self.error[:-1])
            self.sftp.close()
            self.ssh_client.close()

    def do_binnary_backup(self):
        if LooseVersion(self.version) >= LooseVersion("6.13"):
            if config["encrypt"]=="yes":
                if str(config["backup_passwd"])!="":
                    self.ssh_cmd('/system backup save name=/mt-backup.backup dont-encrypt=no password="' + str(config["backup_passwd"]) + '"')
                elif str(config["backup_passwd"]) == "":
                    self.ssh_cmd("/system backup save name=/mt-backup.backup dont-encrypt=no")
            elif config["encrypt"]=="no":
                self.ssh_cmd("/system backup save name=/mt-backup.backup dont-encrypt=yes")
        else:
            self.ssh_cmd("/system backup save name=/mt-backup.backup")
        self.ssh_get_file("mt-backup.backup", os.path.join(config["backup_pth"], self.backup_dir_name, self.timestamp, "mt-backup.backup"))

    def create_backup(self, is_first=False):
        if is_first:
            create_dir(os.path.join(config["backup_pth"], self.backup_dir_name, self.timestamp))
            write_to_file(os.path.join(config["backup_pth"], self.backup_dir_name, self.timestamp, "export.rsc"), self.remote_mt_cfg, "w")
            write_to_file(os.path.join(config["backup_pth"], self.backup_dir_name, "current.rsc"), self.remote_mt_cfg, "w")
            self.do_binnary_backup()
            return 1
        with open (os.path.join(config["backup_pth"], self.backup_dir_name, "current.rsc"), "r") as myfile:
            self.current_config = myfile.read()
        self.diff = difflib.unified_diff(self.current_config.splitlines(), self.remote_mt_cfg.splitlines(), fromfile='Archived config', tofile='Config on router', lineterm='', n=2)        
        self.diff_result = '\n'.join(self.diff)
        if self.diff_result == "":
            self.is_changed = False
            return 0
        else:
            self.is_changed = True
            create_dir(os.path.join(config["backup_pth"], self.backup_dir_name, self.timestamp))
            write_to_file(os.path.join(config["backup_pth"], self.backup_dir_name, self.timestamp, "export.rsc"), self.remote_mt_cfg, "w")
            write_to_file(os.path.join(config["backup_pth"], self.backup_dir_name, "current.rsc"), self.remote_mt_cfg, "w")
            write_to_file(os.path.join(config["backup_pth"], self.backup_dir_name, "diff.log"), ">>> {0} <<< \n".format(self.timestamp) + self.diff_result + "\n\n\n", "a")
            self.do_binnary_backup()
            self.diff_report = self.diff_report_format()
            return 1

    def start_backup_process(self):
        if self.ssh_connect():
            self.identity = self.ssh_cmd(":put [/system identity get name]").rstrip()
            self.serial_number = self.ssh_cmd(":put [/system routerboard get serial-number]").rstrip()
            self.version = self.ssh_cmd(":put [system resource get version]").rstrip()
            self.remote_mt_cfg = '\n'.join(self.ssh_cmd("/export").split('\r\n')[3:])
            self.backup_dir_name = "{0}-{1}-{2}".format(self.ip, self.identity, self.serial_number)
            if not (self.remote_mt_cfg and self.identity and self.version and self.serial_number):
                self.error = "Can't get data from {0}@{1}:{2}\n".format(config['Login'], self.ip, str(self.port))
                if self.verbose: print(self.error[:-1])
                self.ssh_client.close()
                return 0
        else:
            return 0
        create_dir(os.path.join(config["backup_pth"], self.backup_dir_name))
        if os.path.isfile(os.path.join(config["backup_pth"], self.backup_dir_name, "current.rsc")) == False:
            self.create_backup(is_first=True)
            self.ssh_client.close()
            self.duration = datetime.datetime.now() - self.start_time
            print("First time backup for {0}:{1} complete in {2} seconds.".format(self.ip, self.port, int(self.duration.total_seconds())))
            
        else:
            self.create_backup(is_first=False)
            self.ssh_client.close()
            self.duration = datetime.datetime.now() - self.start_time
            print("Backup for {0}:{1} complete in {2} seconds.".format(self.ip, self.port, int(self.duration.total_seconds())))
            

    def diff_report_format(self):
        passwd_pattern = re.compile( '(password=\\W+\S+|password=\S+|authentication-key=\\W+\S+|authentication-key=\S+|wpa2-pre-shared-key=\\W+\S+|wpa2-pre-shared-key=\S+|passphrase=\\W+\S+|passphrase=\S+|secret=\\W+\S+|secret=\S+)' )
        diff_result_without_passwds = passwd_pattern.sub('PASSWD', self.diff_result)
        formatted_string = """
Date: %(date)s
IP: %(ip)s
Router Identity: %(identity)s

%(delta)s
--------------------------------------------------------------
""" % {"date":self.timestamp, "ip":self.ip, "identity":self.identity, "delta":diff_result_without_passwds}
        return formatted_string


def create_dir(path): #Create directory if it not exists
    if os.path.isdir(os.path.join(path)) == False:
        try:
            os.makedirs(os.path.join(path))
        except OSError as err:
             print("---!!! Error: can't create catalog", os.path.join(path), "\n" + str(err))


def write_to_file(path, data, mode): # a - append , w - write
    with open(path, mode) as myfile:
        myfile.write(data)


def open_ssh_key():
    try:
        print("--->>> Try to open key file", config["private_key_file"])
        with open(config["private_key_file"]) as f:
            private_key_type = re.findall(r'^-----BEGIN ([DR]SA) PRIVATE KEY-----$', f.readline())[0]
        if private_key_type == "DSA":
            ssh_key = paramiko.DSSKey.from_private_key_file(config["private_key_file"], password=None)
        elif private_key_type == "RSA":
            ssh_key = paramiko.RSAKey.from_private_key_file(config["private_key_file"], password=None)
        print("--->>> ssh-key loaded. Use key auth")
        return ssh_key
    except IOError:
        print("---!!! Error: can't read private_key_file:", config["private_key_file"])
        sys.exit()
    except IndexError:
        print("---!!! Error: not corrent private_key_file:", config["private_key_file"])
        sys.exit()
    except paramiko.ssh_exception.SSHException as err:
        print("---!!! Error:", err)
        sys.exit()


def sendmail(smtp_serv, login, passwd, mail_from, mail_to, subject, body):
    try:
        server = smtplib.SMTP(smtp_serv)
        server.starttls()
        server.login(login,passwd)
        headers = "From: %s\r\nTo: %s\r\nSubject: %s\r\nX-Mailer: My-Mail\r\n\r\n" % (mail_from, mail_to, subject)
        server.sendmail(mail_from, mail_to, headers + body)
        server.quit()
    except smtplib.SMTPAuthenticationError:
        print("---!!! Error: Can't connect to smtp server: Authentication failed")
    except Exception as err:
        print("---!!! Error: Can't connect to smtp server: " + str(err)) 


def CreateObjectsAndExecute(routerlist):
    ip = routerlist[0][0]
    port = routerlist[0][1]
    #print("Trying to connect to {0}:{1}".format(ip, port))
    routerz.append(Router(ip, port))    
    routerz[-1].start_backup_process()
    sleep(1)

# Start execution #######################
os.system('clear')
script_start_time = datetime.datetime.now()
#paramiko.util.log_to_file("paramiko.log")
print("""
  MMM      MMM       KKK                          TTTTTTTTTTT      KKK
  MMMM    MMMM       KKK                          TTTTTTTTTTT      KKK
  MMM MMMM MMM  III  KKK  KKK  RRRRRR     OOOOOO      TTT     III  KKK  KKK
  MMM  MM  MMM  III  KKKKK     RRR  RRR  OOO  OOO     TTT     III  KKKKK
  MMM      MMM  III  KKK KKK   RRRRRR    OOO  OOO     TTT     III  KKK KKK
  MMM      MMM  III  KKK  KKK  RRR  RRR   OOOOOO      TTT     III  KKK  KKK
------------------------------------------------------------------------------
 backup script by V.Shepelev     ver 1.1 beta                vs@foto-glaz.ru
""")

try:
    routers_list = []
    with open("ip_list.txt") as f:
        for line in f:
            try:
                ip_and_port = re.findall(r'(^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})', line)
                if socket.inet_aton(ip_and_port[0][0]) and int(ip_and_port[0][1]) <= 65535:
                    routers_list.append(ip_and_port)
            except socket.error: pass
            except IndexError: pass
except IOError:
    print("---!!! Error: can't read ip_list.txt")
    sys.exit()

try:
    config = yaml.load(open('config.conf')) 
except IOError:
    print("---!!! Error: can't read config.conf")
    sys.exit()

create_dir(config["backup_pth"])
print("--->>> Connection username:", config['Login'])
print("--->>> Backup storage directory", os.path.join(config["backup_pth"]))

if config['auth_method'] == "key":
    config['pkey'] = open_ssh_key()

if config["encrypt"]=="yes":
    if str(config["backup_passwd"])!="":
        print ("--->>> Backup mode: encryption with password")
    elif str(config["backup_passwd"]) == "":
        print ("--->>> Backup mode: encription without password")
elif config["encrypt"]=="no":
    print ("--->>> Backup mode: without encription")

print("--->>> Number of simultaneous connections (threads):", str(config['threads']))

print("_" * 78)
routerz = []

pool = ThreadPool(int(config['threads']))
pool.map(CreateObjectsAndExecute, routers_list)
pool.close()
pool.join()

failed = [ x.getError() for x in routerz if x.getError() != "" ]
success = [ x.getIPAndPort() for x in routerz if x.getError() == "" ]
changed = [ x.getDiffInfo() for x in routerz if x.getDiffInfo() != "" ]

print("_" * 78)
print("Success tasks:", len(success))
print("".join([" " + x + "\n" for x in success]))

print("Changed configurations:", len(changed))

print("\n")
print("Failed tasks:", len(failed))
print("".join([" " + x for x in failed]))

print("_" * 78)

sctipt_duration = datetime.datetime.now() - script_start_time
print("Script run time: {0} seconds".format(int(sctipt_duration.total_seconds())))
print("_" * 78)            
if changed:
    print("--->>> Sending email diff report")
    sendmail(config["smtp_server"], config["smtp_login"], config["smtp_paswd"], config["email_from"],
                    config["email_to"], "Mikrotik backup script: Configuration is changed", "".join(changed))
if failed:
    print("--->>> Sending email error report")
    sendmail(config["smtp_server"], config["smtp_login"], config["smtp_paswd"], config["email_from"],
                    config["email_to"], "Mikrotik backup script: Error report", "".join(failed)) 