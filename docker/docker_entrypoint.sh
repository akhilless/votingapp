cd /home/votingapp;
python3 manage.py flush --no-input;
python3 /home/votingapp/manage.py migrate auth;
python3 /home/votingapp/manage.py migrate;
python3 manage.py makemigrations voting;
python3 manage.py migrate voting;
python3 /home/votingapp/manage.py createsuperuser --no-input --username votingapp --email votingapp@gmail.com;
python3 manage.py runserver 0.0.0.0:8000;