#!/usr/bin/python
# -*- coding: utf-8 -*-
import socket
import os, sys, subprocess, smtplib
from socket import socket, AF_INET, SOCK_STREAM
from time import localtime, strftime
from distutils.version import LooseVersion

try:
    import paramiko
except ImportError:
    print """
#########################################################
Для работы скрипта нужен модуль paramiko
pip install paramiko
или
apt-get install python-paramiko
#########################################################"""
    sys.exit(1)

try:
    import yaml
except ImportError:
    print """
#########################################################
Для работы скрипта нужен модуль yaml
apt-get install python-yaml
или
pip install pyyaml
#########################################################"""
    sys.exit(1)

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

def do_backup_p(ip_list,login,passwd): # Соединение с аутентификацией по паролю и выполнение операций резервного копирования 
    global ssh_client
    global backup_dir
    global delta_msg_body
    global error_msg_body
    global errors_count
    global ROS_Version    
    date_time=strftime("%d-%m-%Y %H:%M", localtime())                
    
    for line in ip_list:
        try:
            line=line.split(":")
            ip=line[0]
            port=int(line[1])
        except: continue

        if test_port(ip,port)==True:
            print(">>> Подключаюсь к "+login+"@"+ip+":"+str(port))            
            if ssh_connect_p(ip,login,passwd,port)==True:                
                mt_identity=str(ssh_cmd(":put [system identity get name]")).rstrip()
                mt_serial=str(ssh_cmd(":put [/system routerboard get serial-number]")).rstrip()
                ROS_Version=str(ssh_cmd(":put [system resource get version]")).rstrip()
                remote_mt_cfg=ssh_cmd("/export")                
                if remote_mt_cfg==False or mt_identity==False or ROS_Version==False or mt_serial==False or remote_mt_cfg==False:
                    printout ("!!! Не удалось получить данные от роутера.",RED)
                    error_msg_body=error_msg_body+date_time+"   Не удалось получить данные от роутера. "+ login+"@"+ip+":"+str(port)+"\n"
                    errors_count=errors_count+1
                    continue
                backup_dir=str(config["backup_pth"])+"/"+ip+"-"+mt_identity+"-"+mt_serial
                directory_exist(backup_dir)                
                if is_path_exist(backup_dir+"/current.rsc")==0:                    
                    create_backup(date_time,remote_mt_cfg,"newbackup")
                    ssh_client.close()
                    continue
                local_mt_cfg=read_file_to_line(backup_dir+"/current.rsc")                
                if cut_export_header(local_mt_cfg) == cut_export_header(remote_mt_cfg):
                    print (">>> Конфигурация не изменена.")
                    ssh_client.close()
                    continue
                print (">>> Обнаружено изменение конфигурации, создаю бекап...")
                delta=create_backup(date_time,remote_mt_cfg)
                ssh_client.close()
                delta_msg_body=delta_msg_body+delta_report(date_time,ip,mt_identity,mt_serial,delta)                
            else:
                printout ("!!! Не верный логин или пароль для "+login+"@"+ip+":"+str(port), RED)
                error_msg_body=error_msg_body+date_time+"   Не верный логин или пароль для "+ login+"@"+ip+":"+str(port)+"\n"
                errors_count=errors_count+1
        else:
            printout ("!!! Не возможно подключиться к " + ip + ":" + str(port),RED )
            error_msg_body=error_msg_body+date_time+"   Не возможно подключиться к " + ip + ":" + str(port)+"\n"
            errors_count=errors_count+1
    return

def do_backup_k(ip_list,login,ssh_key_pth): # Соединение с аутентификацией по ключу и выполнение операций резервного копирования
    global ssh_client
    global backup_dir
    global delta_msg_body
    global error_msg_body
    global errors_count
    global ROS_Version    
    date_time=strftime("%d-%m-%Y %H:%M", localtime())                
    
    for line in ip_list:
        try:
            line=line.split(":")
            ip=line[0]
            port=int(line[1])
        except: continue
        
        if test_port(ip,port)==True:
            print(">>> Подключаюсь к "+login+"@"+ip+":"+str(port))
            if ssh_connect_k(ip,login,port,ssh_key_pth)==True:
                mt_identity=str(ssh_cmd(":put [system identity get name]")).rstrip()
                mt_serial=str(ssh_cmd(":put [/system routerboard get serial-number]")).rstrip()                
                ROS_Version=str(ssh_cmd(":put [system resource get version]")).rstrip()                
                remote_mt_cfg=ssh_cmd("/export")                
                if remote_mt_cfg==False or mt_identity==False or ROS_Version==False or mt_serial==False or remote_mt_cfg==False:
                    printout ("!!! Не удалось получить данные от роутера.",RED)
                    error_msg_body=error_msg_body+date_time+"   Не удалось получить данные от роутера. "+ login+"@"+ip+":"+str(port)+"\n"
                    errors_count=errors_count+1
                    continue                
                backup_dir=str(config["backup_pth"])+"/"+ip+"-"+mt_identity+"-"+mt_serial                
                directory_exist(backup_dir)                
                if is_path_exist(backup_dir+"/current.rsc")==0:                    
                    create_backup(date_time,remote_mt_cfg,"newbackup")
                    ssh_client.close()
                    continue                
                local_mt_cfg=read_file_to_line(backup_dir+"/current.rsc")                
                if cut_export_header(local_mt_cfg) == cut_export_header(remote_mt_cfg):
                    print (">>> Конфигурация не изменена.")
                    ssh_client.close()
                    continue
                print (">>> Обнаружено изменение конфигурации, создаю бекап...")
                delta=create_backup(date_time,remote_mt_cfg)
                ssh_client.close()
                delta_msg_body=delta_msg_body+delta_report(date_time,ip,mt_identity,mt_serial,delta)                
            else:
                printout ("!!! Не верный логин или SSH ключ для "+login+"@"+ip+":"+str(port), RED)
                error_msg_body=error_msg_body+date_time+"   Не верный логин или SSH ключ для "+ login+"@"+ip+":"+str(port)+"\n"
                errors_count=errors_count+1
        else:
            printout ("!!! Не возможно подключиться к " + ip + ":" + str(port),RED )
            error_msg_body=error_msg_body+date_time+"   Не возможно подключиться к " + ip + ":" + str(port)+"\n"
            errors_count=errors_count+1
    return

def ssh_connect_p(ssh_host,ssh_user,ssh_pass,ssh_port): #функция для подключения по ssh с аутентификацией по паролю
    global ssh_client    
    ssh_client = ""
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_client.connect(hostname=ssh_host,username=ssh_user,password=ssh_pass,port=ssh_port,look_for_keys=False)
        return True        
    except paramiko.AuthenticationException:        
        return False  
    except Exception, e:
        return False

def ssh_connect_k(ssh_host,ssh_user,ssh_port,ssh_key_pth): #функция для подключения по ssh с аутентификацией по ключу
    global ssh_client    
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_key = paramiko.DSSKey.from_private_key_file(ssh_key_pth, password=None)
    except Exception, e:
        print ("!!! Ошибка: " + ssh_key_pth, e)
        return False
    try:
        ssh_client.connect(hostname=ssh_host,username=ssh_user,pkey=ssh_key,port=ssh_port)
        return True
    except Exception, e:
        return False 

def create_backup(date_time,remote_mt_export,new_backup_flag=""): #Функция для создания бекапа    
    delta = ""
    directory_exist(backup_dir+"/"+date_time)    
    print (">>> Делаю export конфигурации в "+backup_dir+"/"+date_time+"/export.rsc")
    write_to_file(backup_dir+"/"+date_time+"/export.rsc",remote_mt_export)
    
    if new_backup_flag!="newbackup":        
        PIPE = subprocess.PIPE
        p = subprocess.Popen("diff --context=1 --ignore-matching-lines='#.*' " + "'" +backup_dir+"/current.rsc"+"' '"+backup_dir+"/"+date_time+"/export.rsc"+"'", shell = True,stdout=subprocess.PIPE)
        s=' '
        while s: 
            s=p.stdout.readline() 
            delta=delta + s

    write_to_file(backup_dir+"/current.rsc",remote_mt_export)        
    
    if LooseVersion(ROS_Version) >= LooseVersion("6.13"):
        if config["encrypt"]==True:
            if str(config["backup_passwd"])!="None":
                ssh_cmd("/system backup save name=mt-backup.backup dont-encrypt=no password=" + str(config["backup_passwd"]))
                print (">>> Создаю бекап с шифрованием и паролем")
            else:
                ssh_cmd("/system backup save name=mt-backup.backup dont-encrypt=no")
                print (">>> Создаю бекап с шифрованием")
        else:
            print (">>> Создаю бекап БЕЗ шифрования и пароля")
            ssh_cmd("/system backup save name=mt-backup.backup")    
    else:
        print (">>> Создаю бекап БЕЗ шифрования и пароля")
        ssh_cmd("/system backup save name=mt-backup.backup")

    print (">>> Сохраняю бинарный бекап в " +backup_dir+"/"+date_time+"/mt-backup.backup")
    ssh_get_file("mt-backup.backup",backup_dir+"/"+date_time+"/mt-backup.backup")
    return delta

def ssh_cmd(ssh_command): #Фукия для выполнения команды по ssh
    global ssh_client
    try:
        stdin, stdout, stderr=ssh_client.exec_command(ssh_command,timeout=10)
        ssh_get_data = stdout.read()    
    except:
        ssh_client.close()
        return False
    return ssh_get_data 

def ssh_get_file(remote_file,local_file): #Функция для получения файла по ssh
    sftp=""
    sftp = ssh_client.open_sftp()
    sftp.get(remote_file,local_file)
    sftp.close() 

def test_port(ssh_host, ssh_port): #функция для проверки открыт ли порт
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect_ex((ssh_host, ssh_port))
        s.close()
        return True       
    except:
        s.close()
        return False 

def write_to_file(path_to_file,that_write): #функция для записи в файл 
    with open(path_to_file, "w") as myfile:
        myfile.write(that_write) 

def readfile(fname): #Читает из файла в переменную-список
    content=[]
    try:
        with open(fname) as f:
            for line in f:
                line=line.rstrip()
                content.append(line)
            return content
    except IOError:
        printout ("!!! Выполнение скрипта невозможно, не могу прочитать файл " + fname, RED)
        exit() 

def read_file_to_line(fname): #читает из файла в строковую переменную
    with open (fname, "r") as myfile:
        data=myfile.read()
        return data 

def is_path_exist(path): #проверяет есть ли файл, если нет, создает его
    if os.path.exists(path):
        if os.path.isfile(path):
            return 1
        elif os.path.isdir(path):
            return 10
    else:
        return 0

def directory_exist(directory): #проверяет существует ли каталог
    if is_path_exist(directory)==10:
        return
    if is_path_exist(directory)==0:
        try:
            os.makedirs(directory)
        except OSError:
            printout ("!!! Не могу создать каталог " + directory, RED) 

def cut_export_header(string): #удаляет 3 верхние строки из export микротика
    out_string = '\n'.join(string.split('\n')[3:]) 
    return out_string 

def sendmail(smtp_serv,login, passwd, mail_from, mail_to,subject,msg): #Функция для отпарвки почты
    try:
        server=smtplib.SMTP(smtp_serv)
        server.starttls()
        server.login(login,passwd)        
        m="From: %s\r\nTo: %s\r\nSubject: %s\r\nX-Mailer: My-Mail\r\n\r\n" % (mail_from, mail_to, subject)
        server.sendmail(mail_from, mail_to, m+msg)
        server.quit()
    except smtplib.SMTPAuthenticationError:
        printout("!!! Невозможно отправить почту, ошибка аутентификации.", RED)
    except Exception, e:
        printout ("!!! Невозможно отравить почту: " + str(e), RED) 

def has_colours(stream): #раскрашивание вывода в консоль
    if not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False 
    try:
        import curses
        curses.setupterm()
        return curses.tigetnum("colors") > 2
    except:
        return False 
has_colours = has_colours(sys.stdout)

def printout(text, colour=WHITE): #Функция для вывода цветных строк в консоль
    if has_colours:
        seq = "\x1b[1;%dm" % (30+colour) + text + "\x1b[0m" + "\n"
        sys.stdout.write(seq)
    else:
        sys.stdout.write(text) 

def delta_report(date,ip,identity,mt_serial,delta): #формирует отчет по разнице в конфигурациях
    msg_body="""
Дата: %(date)s
IP: %(ip)s
Identity: %(identity)s
Serial #: %(mt_serial)s
Diff: %(delta)s
--------------------------------------------------------------
""" % {"date":date,"ip":ip, "identity":identity, "mt_serial":mt_serial, "delta":delta}
    return msg_body



# Отсюда начинается исполнение скрипта.
os.system('clear') 
config = yaml.load(open('config.conf')) 
mt_ip_list = readfile('ip_list.txt')

printout("""
  MMM      MMM       KKK                          TTTTTTTTTTT      KKK
  MMMM    MMMM       KKK                          TTTTTTTTTTT      KKK
  MMM MMMM MMM  III  KKK  KKK  RRRRRR     OOOOOO      TTT     III  KKK  KKK
  MMM  MM  MMM  III  KKKKK     RRR  RRR  OOO  OOO     TTT     III  KKKKK
  MMM      MMM  III  KKK KKK   RRRRRR    OOO  OOO     TTT     III  KKK KKK
  MMM      MMM  III  KKK  KKK  RRR  RRR   OOOOOO      TTT     III  KKK  KKK
------------------------------------------------------------------------------            
              backup script by V.Shepelev 0.8 beta

""",GREEN)

ssh_client =""
error_msg_body=""
errors_count=0
delta_msg_body=""

directory_exist(config["backup_pth"])

if str(config["SSH_key_pth"])=="None":
    print (">>> Инициализирую соединения с использованием аутентификации по паролю")
    do_backup_p(mt_ip_list,str(config["Login"]),str(config["Password"]))
else:
    print (">>> Использую аутентификацию по ключу "+ str(config["SSH_key_pth"]))
    do_backup_k(mt_ip_list,str(config["Login"]),str(config["SSH_key_pth"]))
if len(delta_msg_body) > 10:
    sendmail(str(config["smtp_server"]),str(config["smtp_login"]), str(config["smtp_paswd"]), str(config["email_from"]), str(config["email_to"]),"Mikrotik backup script: Configuration changed",delta_msg_body)
if errors_count >= int(config["errorlevel"]):
    sendmail(str(config["smtp_server"]),str(config["smtp_login"]), str(config["smtp_paswd"]), str(config["email_from"]), str(config["email_to"]),"Mikrotik backup script: Error report",error_msg_body)

