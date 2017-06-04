#template for add credentials to router
#Change password and paste ssh public key
/user add name=backup group=full password="__CHANGE_ME__"
/file print file=public_key_file.txt
:delay 2
/file set public_key_file.txt contents="_PASTE_PUBLIK_KEY_HERE_"
:delay 2
/user ssh-keys import user=backup public-key-file=public_key_file