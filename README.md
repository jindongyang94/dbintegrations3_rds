# multi rds-s3-database-backup

This script allows uploading gzipped rds postgres backups to amazon s3.
Database credentials are retrieved from aws parameter store.


I have changed many of the files here so that you can run more than just one database connection at once using the same sh file by iterating through the json file.
However, please do the following as well:

1. Environment Configured for the AWS User
./aws/config and ./aws/credentials

2. Postgres password file to bypass the need to keep on entering passwords
~/.pgpass → chmod 600
Format: hostname:port:database:username:password
https://www.postgresql.org/docs/10/libpq-pgpass.html


After that you can simply run the python file to run the shell script.

CURRENT UPDATES:

1. I did not utilize the Dockerfile so that might not updated yet. 
2. Need to add checks to buckets so that when it is not created, it can be automatically created for the servers/ databases
3. Code a way to list all needed databases under the server, make them into a dictionary simply based on the host, user and bucket and then do the same functions.