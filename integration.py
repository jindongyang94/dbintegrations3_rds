import os
import json
import subprocess

import boto3
import psycopg2

"""
The idea of this file is to create and update the environment variables iteratively, and the 
script can be used to run the bash file found online. 

The environment variables would be put together based on what is written in the json. 

Upload the file downloaded to s3 to the correct respective folders and buckets based on company
name. It is important to note that the files with the same name would be replaced. This would 
help in not saving redundant files but might not be useful if we want to version.

S3 files would be named as follows: 
s3://{BucketName-(Data Lake)}/{CompanyName}/{ModuleName}/{TableName}.csv

"""

with open("info.json", "r") as credentials:
    creds = json.load(credentials)

# This method only allows you to import and dump the databases as a sql file for every database in your db instance
for key, value in creds.items():

    database_listcall = ['psql', '-h' ,value['database-host'], '-p', '5432', '-U', value['database-user'], value['database-name'], '-c', 'SELECT datname FROM pg_catalog.pg_database']
    database_list = subprocess.check_output(database_listcall).decode('utf-8')
    # This removes all of the unnecesary information from the text to obtain only the database names
    database_list = list(filter(None, database_list.split('\n')[2:-3]))
    database_list = list(map(lambda x: x.strip(), database_list))
    for database_name in database_list:

        # This removes all of the default databases which we should ignore
        if database_name.lower() not in ['postgres', 'rdsadmin', 'template1', 'template0']:

            os.environ['IDENTIFIER'] = key
            os.environ['DATABASE_HOST'] = value['database-host']
            os.environ['DATABASE_USER'] = value['database-user']
            os.environ['DATABASE_NAME'] = database_name
            os.environ['S3_BUCKET'] = value['s3-bucket']






