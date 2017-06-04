#Скрипт для резервного копирования конфигураций роутеров на MikroTik RouterOS.

***
##Особенности:
* Делает резервные копии, только если конфигурация была изменена;
* Обеспечивает версионность резервных копий;
* Не производит запись на накопитель роутера без необходимости;
* Оповещает по email об изменении конфигураций (со списком изменений) и об ошибках.
* Поддерживает возможность шифрования бекапов (средствами RouterOS)
* Записывает изменение конфигурации в log файл
* Поддерживает аутентификацию по RSA\DSA ssh ключам.
* Работает под Linux и под Windows
* Рекомендуемая версия python 3.6 + (но на 2.7 тоже работает) 

##Базовая настройка
1. Для работы скрипта необходимо установить: **python python-dev python-yaml git python-pip paramiko**
	
	Через пакетный менеджер:  
	`sudo apt-get install python python-dev python-yaml python-pip git`

	Или через PIP:  
	`sudo pip install paramiko pyyaml`

	Если у вас старый модуль paramiko, то желательно его обновить
	`sudo  pip install paramiko --upgrade`
	

2. Рекомендуется создать отдельного пользователя, под которым будет работать скрипт ,например, пользователя mt  
	`adduser mt`

3. Переключаемся на свежесозданного пользователя и копируем себе скрипт  
	`su - mt`  
	`git clone https://github.com/0x566164696D/mt_backup_ng.git`  
	`cd mt_backup_ng`

4. Выполняем настройку скрипта, переименовываем config.conf.example в config.conf редактируем его. Переименовываем 	ip_list.txt.example в ip_list.txt и вносим в него IP адреса и порты маршрутизаторов.  
	`cp ip_list.txt.example ip_list.txt; cp config.conf.example config.conf`  
	Внимание! На каждой строке должно быть по одному IP адресу.
	Обязательно нужно указывать порт через двоеточие!  
	Например:  
	`192.168.0.254:22`  
	`192.168.1.254:22`  
	`192.168.2.254:8022` 

6. Запускаем скрипт командой:  
	`python backup.py`

##Аутентификация по ключу
RouterOS поддерживает DSA и RSA ключи. Поддержка RSA ключей реализована начиная с версии 6.31
Использование RSA ключей предпочтительней.

1. Если требуется аутентификация по ключу, создаем приватный и публичный ключ  
	Для DSA:  
	 `ssh-keygen -t dsa -C _комментарий_`
	
	Для RSA:  
	`ssh-keygen -C _комментарий_`  
	
	Если планируется запуск скрипта через планировщик, лучше не ставить пароль на приватный ключ.

2. Прописываем в конфигурационном файле config.conf путь до свежесозданного приватного ключа и логин, под которым мы впоследствии будем подключаться к роутерам.  
	Путь должен быть либо абсолютным, типа `/home/mt/.ssh/id_rsa`, либо относительным `../.ssh/id_dsa`  
	Ипользованеи `~` при указании пути работать не будет.

3. Теперь на роутерах нужно создать пользователя и установить публичный ключ. Для этого в текстовом редакторе создаем файл следующего содержимого:  
	`/user add name=backup group=full password=_change_me!_`  
	`/file print file=dsa_pub`  
	`:delay 2`  
	`/file set dsa_pub.txt contents="___ТУТ_НУЖНО_ВПИСАТЬ_ПУБЛИЧНЫЙ_КЛЮЧ_ _СКОПИРУЙТЕ_СОДЕРЖИМОЕ_ИЗ_ФАЙЛА_~/.ssh/id_dsa.pub___"`  
	`:delay 2`  
	`/user ssh-keys import user=backup public-key-file=dsa_pub.txt`  
	
	Должно получится что-то типа:  
	`/user add name=backup group=full password=SJ^2BJ2!Smn829QZ`  
	`/file print file=dsa_pub`  
	`:delay 2`  
	`/file set dsa_pub.txt contents="ssh-dss AAAAB3NzaC1kc3MAAACBAIGoPsxbmGOEF9cXLJvKpzIn58mD0HiTxF/WXdF6Xq93l4AbdLB5dji1WEvG2d603IRlauqt2/icxKrRy9I/7Fa7NVxB6CazN6v/omSGOKeWYFSjfypfdXgrASCdvDpER4lhMBJHWF4DlJUEQm+ZmgFAK3bgSfA9B4rELSLhGvRFAAAAFQC1x27O2WYVu6CGgUEWijUg4UzHBQAAAIAM6qb9P09FJ1hPgETAPSlK/S21uwnjNsjXbv5RwtbZ7yMrrcnhfOZ18nL2EprsVK+MG+YY8/auS5yi0dSBVgUH5XTqNPURziKvLoAdh+PNavy1dgAJvSbNK6yVlFUK/HbwOFAhm3S27cYxSIr6zkDuu8qxMFh7D8TdSmqzSgdoKgAAAIAzG9vG7oOEpNDImtCrtaARSb+wgJshCEgyRLLhT8N/BgYTDJUsMEJvHJCYgSsz1W55FebNkxS8huzkj7i0bs969Mk7jDBxKRTPNMvoFonmOlmhnXCjRt2F8qIIgSJ/BkXd/+7JbynvbvVSozv7PfMdMbUV8F4dABC6+fTZiQXQfw== comment"`  
	`:delay 2`  
	`/user ssh-keys import user=backup public-key-file=dsa_pub.txt`
	
	Подобный текстовый файл уже лежит в каталоге со скриптом - 
	`add_backup_user.rsc`


4. Далее нужно залить этот файл на роутер и применить его командой  
	`/import file=имя_файла`  
или просто скопировать содержимое файла в консоль роутера.

##Запуск скрипта по расписанию
1. Откройте планировщик cron  
	`crontab -e`

2. И добавьте следующее:  
	`0 0 * * * cd /home/mt/mt_backup_ng/ && /usr/bin/python backup.py`  
В конце расписания cron должна быть пустая строка.  
В таком случае скрипт будет запускаться каждый день в 00:00

##Обновление с предыдущей версии
1. Сделайте резервную копию файлов config.conf и ip_list.txt
2. Перейдите в каталог со скриптом и сделайте `git pull`
3. Если git pull выдаст ошибку, то проще всего установить скрипт заново
3. Синтаксис файла config.conf изменился, отредактируйте свой конфиг на примере config.conf.example.

Поскольку заголовок в export (первые три строки, которые содержат дату экспорта, версию ROS и software ID) теперь не сохраняется, то при первом запуске нового скрипта со старой базой бекапов вы получите сообщение об изменении конфигурации.