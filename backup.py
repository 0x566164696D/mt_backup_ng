#!/usr/bin/python
import os
import sys 
import subprocess
import smtplib
import re
import socket
import difflib
from time import localtime, strftime
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

def create_dir(path): #Create directory if it not exists
    if os.path.isdir(os.path.join(path)) == False:
        try:
            os.makedirs(os.path.join(path))            
        except OSError as err:
             print("---!!! Error: can't create catalog", os.path.join(path), "\n" + str(err))
    

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


def ssh_connect(ssh_host, ssh_port):
    global ssh_client 
    global errors_email_report_body  
    ssh_client = None
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())    
    try:
        if config['auth_method'] == "key": 
            ssh_client.connect(hostname=ssh_host, port=int(ssh_port), timeout=3,
                                username=config['Login'],pkey=config['pkey'])
            print("--->>> Connection to {0}@{1}:{2} established".format(config['Login'], ssh_host, str(ssh_port)))
        else:
            ssh_client.connect(hostname=ssh_host, port=int(ssh_port), timeout=3, look_for_keys=False, allow_agent=False,
                                username=config['Login'], password=config['Password'])
            print("--->>> Connection to {0}@{1}:{2} established".format(config['Login'], ssh_host, str(ssh_port)))
        return True
    except paramiko.AuthenticationException:
        error_msg = "---!!! Error: Can't connect to {0}:{1}, Authentication failed \n".format(ssh_host, ssh_port)
        print(error_msg)
        errors_email_report_body += error_msg
    except paramiko.SSHException:
        error_msg = "---!!! Error: Can't connect to {0}:{1}, SSHException. Maybe key auth failed\n".format(ssh_host, ssh_port)
        print(error_msg)
        errors_email_report_body += error_msg
    except Exception as err:
        error_msg = "---!!! Error: Can't connect to {0}:{1}, {2}\n".format(ssh_host, ssh_port, err)
        print(error_msg)
        errors_email_report_body += error_msg
    return False 


def ssh_cmd(ssh_command):
    global ssh_client    
    try:
        stdin, stdout, stderr=ssh_client.exec_command(ssh_command, timeout=15)
        ssh_get_data = stdout.read()
        return ssh_get_data.decode('utf-8')
    except Exception as err:        
        print("---!!! Error: Can't send command to router", err)
        print("\n")
        ssh_client.close()
        return ""


def ssh_get_file(remote_file, local_file):
    sftp=""
    try:
        sftp = ssh_client.open_sftp()
        sftp.get(remote_file, local_file)
        sftp.close()
    except Exception as err:
        print("---!!! Error:", err)
        sftp.close()


def do_backup():    
    global error_msg_body
    global errors_email_report_body
    global ssh_client   
    for _ in routers_list:        
        ip = _[0][0]        
        port = _[0][1]
        timestamp = strftime("%d-%m-%Y (%H-%M)", localtime())
        if ssh_connect(ip, port):
            identity = ssh_cmd(":put [/system identity get name]").rstrip()
            serial_number = ssh_cmd(":put [/system routerboard get serial-number]").rstrip()
            version = ssh_cmd(":put [system resource get version]").rstrip()                        
            remote_mt_cfg = '\n'.join(ssh_cmd("/export").split('\r\n')[3:])            
            backup_dir_name = "{0}-{1}-{2}".format(ip, identity, serial_number)            
            if not (remote_mt_cfg and identity and version and serial_number):
                error_message = "---!!! Error: can't get data from {0}@{1}:{2}\n".format(config['Login'], ip, str(port))
                errors_email_report_body += error_message                
                ssh_client.close()
                continue             
            create_dir(os.path.join(config["backup_pth"], backup_dir_name))
            if os.path.isfile(os.path.join(config["backup_pth"], backup_dir_name, "current.rsc")) == False:                
                create_backup(timestamp, ip, identity, backup_dir_name, remote_mt_cfg, version, is_first=True)
                ssh_client.close()
                continue
            else:                
                create_backup(timestamp, ip, identity, backup_dir_name, remote_mt_cfg, version, is_first=False)
                ssh_client.close()            


def write_to_file(path, data, mode): # a - append , w - write
    with open(path, mode) as myfile:
        myfile.write(data)


def create_backup(timestamp, ip, identity, backup_dir_name, remote_mt_cfg, version, is_first=False):
    global diff_email_report_body
    if is_first:
        print("--->>> Create first time backup\n")
        create_dir(os.path.join(config["backup_pth"], backup_dir_name, timestamp))    
        write_to_file(os.path.join(config["backup_pth"], backup_dir_name, timestamp, "export.rsc"), remote_mt_cfg, "w")
        write_to_file(os.path.join(config["backup_pth"], backup_dir_name, "current.rsc"), remote_mt_cfg, "w")
        do_binnary_backup(timestamp, backup_dir_name, version)
        return 1
    with open (os.path.join(config["backup_pth"], backup_dir_name, "current.rsc"), "r") as myfile:
        current_config = myfile.read()
    diff = difflib.unified_diff(current_config.splitlines(), remote_mt_cfg.splitlines(), fromfile='Archived config', tofile='Config on router', lineterm='', n=2)        
    diff_result = '\n'.join(diff)
    if diff_result == "":
        print("--->>> No changes detected...\n")
        return 0
    else:
        print("--->>> Config is changed. Start backup...\n")
        create_dir(os.path.join(config["backup_pth"], backup_dir_name, timestamp))    
        write_to_file(os.path.join(config["backup_pth"], backup_dir_name, timestamp, "export.rsc"), remote_mt_cfg, "w")
        write_to_file(os.path.join(config["backup_pth"], backup_dir_name, "current.rsc"), remote_mt_cfg, "w")
        write_to_file(os.path.join(config["backup_pth"], backup_dir_name, "diff.log"), ">>> {0} <<< \n".format(timestamp) + diff_result + "\n\n\n", "a")
        do_binnary_backup(timestamp, backup_dir_name, version)
        diff_email_report_body += diff_report_format(timestamp, ip, identity, diff_result)        
        return 1


def do_binnary_backup(timestamp, backup_dir_name, version):
    if LooseVersion(version) >= LooseVersion("6.13"):        
        if config["encrypt"]=="yes":        
            if str(config["backup_passwd"])!="":
                ssh_cmd('/system backup save name=/mt-backup.backup dont-encrypt=no password="' + str(config["backup_passwd"]) + '"')                                
            elif str(config["backup_passwd"]) == "":
                ssh_cmd("/system backup save name=/mt-backup.backup dont-encrypt=no")                
        elif config["encrypt"]=="no":            
            ssh_cmd("/system backup save name=/mt-backup.backup dont-encrypt=yes")    
    else:        
        ssh_cmd("/system backup save name=/mt-backup.backup")
    #print ("--->>> Save backup to ", os.path.join(config["backup_pth"], backup_dir_name, timestamp, "mt-backup.backup"))
    ssh_get_file("mt-backup.backup", os.path.join(config["backup_pth"], backup_dir_name, timestamp, "mt-backup.backup"))    


def diff_report_format(timestamp, ip, identity, diff_result):
    passwd_pattern = re.compile( '(password=\\W+\S+|password=\S+|authentication-key=\\W+\S+|authentication-key=\S+|wpa2-pre-shared-key=\\W+\S+|wpa2-pre-shared-key=\S+|passphrase=\\W+\S+|passphrase=\S+|secret=\\W+\S+|secret=\S+)' )
    diff_result_without_passwds = passwd_pattern.sub('PASSWD', diff_result)
    formatted_string = """
Date: %(date)s
IP: %(ip)s
Router Identity: %(identity)s

%(delta)s
--------------------------------------------------------------
""" % {"date":timestamp, "ip":ip, "identity":identity, "delta":diff_result_without_passwds}
    return formatted_string


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


# Start execution #######################
os.system('clear') 
print("""
  MMM      MMM       KKK                          TTTTTTTTTTT      KKK
  MMMM    MMMM       KKK                          TTTTTTTTTTT      KKK
  MMM MMMM MMM  III  KKK  KKK  RRRRRR     OOOOOO      TTT     III  KKK  KKK
  MMM  MM  MMM  III  KKKKK     RRR  RRR  OOO  OOO     TTT     III  KKKKK
  MMM      MMM  III  KKK KKK   RRRRRR    OOO  OOO     TTT     III  KKK KKK
  MMM      MMM  III  KKK  KKK  RRR  RRR   OOOOOO      TTT     III  KKK  KKK
------------------------------------------------------------------------------            
 backup script by V.Shepelev ver1.0                         vs@foto-glaz.ru
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


diff_email_report_body = ""
errors_email_report_body = ""
print("\n" + "-" * 78 + "\n")

do_backup()

if diff_email_report_body:    
    print("--->>> Sending email diff report")
    sendmail(config["smtp_server"], config["smtp_login"], config["smtp_paswd"], config["email_from"],
                    config["email_to"], "Mikrotik backup script: Configuration is changed", diff_email_report_body)
if errors_email_report_body:
    print("--->>> Sending email error report")
    sendmail(config["smtp_server"], config["smtp_login"], config["smtp_paswd"], config["email_from"],
                    config["email_to"], "Mikrotik backup script: Error report", errors_email_report_body)