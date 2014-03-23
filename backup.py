#!/usr/bin/python
# -*- coding: utf-8 -*-
import os, sys, yaml, paramiko, socket, getpass, sys, subprocess,smtplib
from socket import socket, gethostbyname, AF_INET, SOCK_STREAM
from time import gmtime, localtime, strftime
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
#ФУНКЦИИ
# Соединение с аутентификацией по паролю и выполнение операций резервного копирования
def do_backup_p(ip_list,login,passwd):
    global backup_dir
    global delta_msg_body
    global error_msg_body
    global errors_count
    error_msg_body=""
    errors_count=0
    delta_msg_body=""    
    date_time=strftime("%d-%m-%Y %H:%M", localtime())                
    for line in ip_list:
        line=line.split(":")
        ip=line[0]
        port=int(line[1])        
        if test_port(ip,port)==True:
            print("Поключаюсь к "+login+"@"+ip+":"+str(port))
            if ssh_connect_p(ip,login,passwd,port)==True:                
                mt_identity=identity_parse(ssh_cmd("/system identity print"))
                mt_serial=ssh_cmd(":put [/system routerboard get serial-number]")[1:].rstrip()                
                backup_dir=str(config["backup_pth"])+"/"+ip+"-"+mt_identity+"-"+mt_serial                
                directory_exist(backup_dir)                
                if is_path_exist(backup_dir+"/current.rsc")==0:
                    remote_mt_cfg=cut_export_header(ssh_cmd("/export"))
                    create_backup(remote_mt_cfg,date_time,"newbackup")
                    ssh_client.close()
                    continue
                local_mt_cfg=read_file_to_line(backup_dir+"/current.rsc")
                remote_mt_cfg=cut_export_header(ssh_cmd("/export"))
                if local_mt_cfg == remote_mt_cfg:
                    print ("Конфигурация не изменена.")
                    ssh_client.close()
                    continue
                print ("Обнаружено изменение конфигурации, создаю резервную копию...")
                delta=create_backup(remote_mt_cfg,date_time)                
                ssh_client.close()
                delta_msg_body=delta_msg_body+delta_report(date_time,ip,mt_identity,mt_serial,delta)
                print delta_msg_body
            else:
                printout ("Неверный пароль для "+login+"@"+ip+":"+str(port), RED)
                error_msg_body=error_msg_body+date_time+"   Неверный пароль для "+ login+"@"+ip+":"+str(port)+"\n"
                errors_count=errors_count+1
        else:
            printout ("Не могу подключиться к " + ip + ":" + str(port),RED )
            error_msg_body=error_msg_body+date_time+"   Не могу подключиться к " + ip + ":" + str(port)+"\n"
            errors_count=errors_count+1
    return 
# Соединение с аутентификацией по ключу и выполнение операций резервного копирования
def do_backup_k(ip_list,login,ssh_key_pth):
    global backup_dir
    global delta_msg_body
    global error_msg_body
    global errors_count
    error_msg_body=""
    errors_count=0
    delta_msg_body=""    
    date_time=strftime("%d-%m-%Y %H:%M", localtime())                
    for line in ip_list:
        line=line.split(":")
        ip=line[0]
        port=int(line[1])        
        if test_port(ip,port)==True:
            print("Поключаюсь к "+login+"@"+ip+":"+str(port))
            if ssh_connect_k(ip,login,port,ssh_key_pth)==True:
                mt_identity=identity_parse(ssh_cmd("/system identity print"))
                mt_serial=ssh_cmd(":put [/system routerboard get serial-number]")[1:].rstrip()                
                backup_dir=str(config["backup_pth"])+"/"+ip+"-"+mt_identity+"-"+mt_serial                
                directory_exist(backup_dir)                
                if is_path_exist(backup_dir+"/current.rsc")==0:
                    remote_mt_cfg=cut_export_header(ssh_cmd("/export"))
                    create_backup(remote_mt_cfg,date_time,"newbackup")
                    ssh_client.close()
                    continue
                local_mt_cfg=read_file_to_line(backup_dir+"/current.rsc")
                remote_mt_cfg=cut_export_header(ssh_cmd("/export"))
                if local_mt_cfg == remote_mt_cfg:
                    print ("Конфигурация не изменена.")
                    ssh_client.close()
                    continue
                print ("Обнаружено изменение конфигурации, создаю резервную копию...")
                delta=create_backup(remote_mt_cfg,date_time)                
                ssh_client.close()
                delta_msg_body=delta_msg_body+delta_report(date_time,ip,mt_identity,mt_serial,delta)
                print delta_msg_body
            else:
                printout ("Неверный логин\ключ для "+login+"@"+ip+":"+str(port), RED)
                error_msg_body=error_msg_body+date_time+"   Неверный логин\ключ для "+ login+"@"+ip+":"+str(port)+"\n"
                errors_count=errors_count+1
        else:
            printout ("Не могу подключиться к " + ip + ":" + str(port),RED )
            error_msg_body=error_msg_body+date_time+"   Не могу подключиться к " + ip + ":" + str(port)+"\n"
            errors_count=errors_count+1
    return 
#функция для подключения по ssh с аутентификацией по паролю
def ssh_connect_p(ssh_host,ssh_user,ssh_pass,ssh_port):
    global ssh_client
    ssh_client =""
    ssh_client = paramiko.SSHClient()    
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_client.connect(hostname=ssh_host,username=ssh_user,password=ssh_pass,port=ssh_port)
        return True        
    except paramiko.AuthenticationException:
        return False
#функция для подключения по ssh с аутентификацией по ключу
def ssh_connect_k(ssh_host,ssh_user,ssh_port,ssh_key_pth):
    global ssh_client
    ssh_client = ""
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_key = paramiko.DSSKey.from_private_key_file(ssh_key_pth, password=None)
    except Exception, e:
        print ("ERROR: " + ssh_key_pth, e)
        return False
    try:
        ssh_client.connect(hostname=ssh_host,username=ssh_user,pkey=ssh_key,port=ssh_port)
        return True
    except Exception, e:
        return False
#Функция для создания бекапа
def create_backup(remote_mt_export,date_time,new_backup_flag=""):    
    delta=""
    directory_exist(backup_dir+"/"+date_time)    
    print (backup_dir+"/"+date_time+"/export.rsc")
    write_to_file(backup_dir+"/"+date_time+"/export.rsc",remote_mt_export)
    if new_backup_flag!="newbackup":        
        PIPE = subprocess.PIPE
        p = subprocess.Popen("diff '"+backup_dir+"/current.rsc"+"' '"+backup_dir+"/"+date_time+"/export.rsc"+"'", shell = True,stdout=subprocess.PIPE)
        s=' '
        while s: 
            s=p.stdout.readline() 
            delta=delta + s                
    print (backup_dir+"/current.rsc")
    write_to_file(backup_dir+"/current.rsc",remote_mt_export)        
    ssh_cmd("/system backup save name=mt-backup.backup")
    print (backup_dir+"/"+date_time+"/mt-backup.backup")
    ssh_get_file("mt-backup.backup",backup_dir+"/"+date_time+"/mt-backup.backup")
    return delta
#Фукия для выполнения комvанды по ssh
def ssh_cmd(ssh_command):
    stdin, stdout, stderr=ssh_client.exec_command(ssh_command)
    ssh_get_data = stdout.read()
    return ssh_get_data
#Функция для получения файла по ssh
def ssh_get_file(remote_file,local_file):
    sftp=""
    sftp = ssh_client.open_sftp()
    sftp.get(remote_file,local_file)
    sftp.close()
#Фунция для разбора строки с identity с микротика
def identity_parse(in_str):
    split=in_str.split(":")
    identity=split[1]
    return identity[1:].rstrip()
#функция для проверки открыт ли порт
def test_port(ssh_host, ssh_port):
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(3)
    result = s.connect_ex((ssh_host, ssh_port))
    if(result == 0) :
        s.close()
        return True
    else:
        s.close()
        return False
#функция для записи в файл 
def write_to_file(path_to_file,that_write):
    with open(path_to_file, "w") as myfile:
        myfile.write(that_write)
#Читает из файла в переменную-список
def readfile(fname):
    content=[]
    try:
        with open(fname) as f:
            for line in f:
                line=line.rstrip()
                content.append(line)
            return content
    except IOError:
        print ("Выполнение скрипта невозможно, не могу прочитать файл " + fname)
        exit()
#читает из файла в строковую переменную
def read_file_to_line(fname):
    with open (fname, "r") as myfile:
        data=myfile.read()
        return data
#проверяет есть ли файл, если нет, создает его
def is_path_exist(path):
    if os.path.exists(path):
        if os.path.isfile(path):
            return 1
        elif os.path.isdir(path):
            return 10
    else:
        return 0
#проверяет существует ли каталог
def directory_exist(directory):
    if is_path_exist(directory)==10:
        return
    if is_path_exist(directory)==0:
        try:
            os.makedirs(directory)
        except OSError:
            print ("Не могу создать каталог " + directory)
#удаляет 3 верхние строки из export микротика
def cut_export_header(string):
    out_string = '\n'.join(string.split('\n')[3:]) 
    return out_string
#Функция для отпарвки почты
def sendmail(smtp_serv,login, passwd, mail_from, mail_to,subject,msg):
    try:
        server=smtplib.SMTP(smtp_serv)
        server.starttls()
        server.login(login,passwd)        
        m="From: %s\r\nTo: %s\r\nSubject: %s\r\nX-Mailer: My-Mail\r\n\r\n" % (mail_from, mail_to, subject)
        server.sendmail(mail_from, mail_to, m+msg)
        server.quit()
    except smtplib.SMTPAuthenticationError:
        print("Невозможно отправить почту, ошибка аутентификации.")
#раскрашивание вывода в консоль
def has_colours(stream):
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
#Функция для вывода цветных строк в консоль
def printout(text, colour=WHITE):
    if has_colours:
        seq = "\x1b[1;%dm" % (30+colour) + text + "\x1b[0m" + "\n"
        sys.stdout.write(seq)
    else:
        sys.stdout.write(text)
#формирует отчет по разнице в конфигурациях
def delta_report(date,ip,identity,mt_serial,delta):
    msg_body="""
Дата: %(date)s
IP: %(ip)s
Identity: %(identity)s
Serial #: %(mt_serial)s
Diff: %(delta)s
--------------------------------------------------------------
""" % {"date":date,"ip":ip, "identity":identity, "mt_serial":mt_serial, "delta":delta}
    return msg_body

#Конец функций
#########################################################################################
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
              backup script by V.Shepelev 0.6 beta

""",GREEN)

directory_exist(config["backup_pth"])
if str(config["SSH_key_pth"])=="None":
    print ("Инициализирую соединения с использованием аутентификации по паролю")
    do_backup_p(mt_ip_list,str(config["Login"]),str(config["Password"]))
else:
    print ("Инициализирую соединения с использованием аутентификации по DSA ключу "+ str(config["SSH_key_pth"]))
    do_backup_k(mt_ip_list,str(config["Login"]),str(config["SSH_key_pth"]))
if len(delta_msg_body) > 10:
    sendmail(str(config["smtp_server"]),str(config["smtp_login"]), str(config["smtp_paswd"]), str(config["email_from"]), str(config["email_to"]),"Mikrotik backup script: Configuration changed",delta_msg_body)
if errors_count > int(config["errorlevel"]):
    sendmail(str(config["smtp_server"]),str(config["smtp_login"]), str(config["smtp_paswd"]), str(config["email_from"]), str(config["email_to"]),"Mikrotik backup script: Error report",error_msg_body)

