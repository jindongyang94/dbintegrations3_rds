# multi rds-s3-database-copy
This script can also be done locally as well. 

Method 1: (integration.py) - Backup
You can run more than just one database connection at once using the same sh file by iterating through the json file. However, this can only be used to dump .sql files for backup.
However, please do the following as well (especially if you are running this locally):

1. Environment Configured for the AWS User
./aws/config and ./aws/credentials - configure them the same as AWS website asked you.
Ensure that you have the correct permissions tagged to this user as well, primarily S3 and RDS access.

2. Postgres password file to bypass the need to keep on entering passwords
~/.pgpass → chmod 600
Format: hostname:port:database:username:password
https://www.postgresql.org/docs/10/libpq-pgpass.html
If the username and password are going to be the same for all databases/host, you can simply put *:*:*:username:password

If you are doing this on Lambda or EC2 instance, database and user credentials can be retrieved from the aws parameter store. 

3. Maintain the JSON file as per given in the example.json: Change the values with 'fake' in its name.

After that you can simply run the python file to run the shell script.

Method 2: (integration2.py) - Export
I have created another way using Boto3 and Psycopg2, which now does not require you to utilize a JSON file to maintain the host/ port/ user etc. However, you do have to perform the same configurations as stated above. This method also allows you to export the database to as a CSV file. You can change it however, if you want it to dump a .sql file as above as well. However, there are additional requirements due to the usage of python modules:

1. Please install Boto3 and Psycopg2 as per instructed in the requirements.txt using pip install -r requirements.txt




-------------------------------------------------------------------------------------------------------------------------------------------------------------------
The dockerfile now satisfy both requirements so you can use that to spin the container needed for both scripts. Both methods can be used interchangeably for your best results. For example, you can still use method 2 so you do not have to maintain a JSON file, but at the same time you can use the shell script in method 1 to back up as a .sql file.

CURRENT UPDATES:

1. Need to add checks to buckets so that when it is not created, it can be automatically created for the servers/ databases. Right now, you still have to make sure that the bucket names exist. The name formulation is s3://{BucketName-(Data Lake)}/{CompanyName}/{ModuleName}/{TableName}.csv
