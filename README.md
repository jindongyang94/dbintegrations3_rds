# Multi RDS - S3 Extraction Pipeline

---

This script can also be done locally as well.

## Test Scripts

### Method 1 - Bash Script

You can run more than just one database connection at once using the same sh file by iterating through the json file. However, this can only be used to dump .sql files for backup.  
However, please do the following as well (especially if you are running this locally):

* Environment Configured for the AWS User  
./aws/config and ./aws/credentials - configure them the same as AWS website asked you.  
* Ensure that you have the correct permissions tagged to this user as well, primarily S3 and RDS access.
Postgres password file to bypass the need to keep on entering passwords  
~/.pgpass → chmod 600  
* Format: hostname:port:database:username:password  
If the username and password are going to be the same for all databases/host, you can simply put "*amp:*:*:username:password"  
If you are doing this on Lambda or EC2 instance, database and user credentials can be retrieved from the aws parameter store.
* Maintain the JSON file as per given in the example.json: Change the values with 'fake' in its name.

After that you can simply run the python file to run the shell script.

### Method 2 - Python Script

I have created another way using Boto3 and Psycopg2, which now does not require you to utilize a JSON file to maintain the host/ port/ user etc. However, you do have to perform the same configurations as stated above.  
This method also allows you to export the database to as a CSV file.  
You can change it however, if you want it to dump a .sql file as above as well. However, there are additional requirements due to the usage of python modules:

* Please install Boto3 and Psycopg2 as per instructed in the requirements.txt using pip install -r requirements.txt

===

## Production Scripts

### Daily Integration File

The purpose of this file is to allow you to do daily migration locally or on Lambda. However, for Lambda, you need to set up environmental variables to store the PostGres password as well as the dependencies needed to run the script (psycopg2)

### Periodic Dump File

This script would just a simplified version of what is created initially. This will do an indiscriminate dump of all the tables to ensure the files maintained in the raw data lake is always accurate.

* Please install Boto3 and Psycopg2 as per instructed in the requirements.txt using pip install -r requirements.txt

* Environment Configured for the AWS User  
./aws/config and ./aws/credentials - configure them the same as AWS website asked you.  
Ensure that you have the correct permissions tagged to this user as well, primarily S3 and RDS access.

* Postgres password file to bypass the need to keep on entering passwords  
~/.pgpass → chmod 600  
Format: hostname:port:database:username:password  
[Reference Tutorial](https://www.postgresql.org/docs/10/libpq-pgpass.html)
If the username and password are going to be the same for all databases/host, you can simply put "*amp:*:*:username:password"  

If you are doing this on Lambda or EC2 instance, database and user credentials can be retrieved from the aws parameter store.

* Maintain the JSON file as per given in the example.json: Change the values with 'fake' in its name.

*There is no need for a dockerfile for production scripts right now as we are not planning to spin up an instance. However, if next time this is needed, we can add one to ensure the dependencies are met.*
