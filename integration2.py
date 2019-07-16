import subprocess

import boto3
import psycopg2

"""
The idea of this script is to find the respective database instances using Boto3, and then find the 
respective databases in the instance and finally find the respective tables in each database and do a iterative
export and dump one table at a time to prevent overloading of memory.

This process can be expedited by parallel processing but I am unsure of how to do so yet. Would figure out a way
if this becomes a pertinent issue. 

Upload the file downloaded to s3 to the correct respective folders and buckets based on company
name. It is important to note that the files with the same name would be replaced. This would 
help in not saving redundant files but might not be useful if we want to version.

S3 files would be named as follows: 
s3://{BucketName-(Data Lake)}/{CompanyName}/{ModuleName}/{TableName}.csv

"""

# This method allows me to connect to export csv files for each table. 
# This method does not require the maintenance of a JSON file at all, just different AWS credentials
# needed for different servers if different users have different access to the databases. 


rds = boto3.client('rds')
dbs = rds.describe_db_instances()['DBInstances']
for db in dbs:
    dbname = db['DBInstanceIdentifier']
    dbuser = db['MasterUsername']
    endpoint = db['Endpoint']
    host = endpoint['Address']
    port = endpoint['Port']

    print(dbuser)
    print(endpoint)
    con = psycopg2.connect(dbname='postgres', host=host, port=port, user=dbuser)
    cur = con.cursor()
    
    #list all available databases in the same instance

    def store_query(title, qry):
        print('%s' % (title))
        cur.execute(qry)
        result = []
        for row in cur.fetchall():
            result.append(row)
        return result

    databases = store_query('listing databases', 'SELECT * FROM pg_database')
    database_names = list(map(lambda x: x[0], databases))

    for database_name in database_names:
        if database_name.lower() not in ['postgres', 'rdsadmin', 'template1', 'template0']:

            table_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            tables = store_query('listing tables', table_query)
            table_names = list(map(lambda x: x[0], tables))

            for table_name in table_names:

                export_query = "SELECT * FROM " + table_name

                with open("/mnt/results/month/table.csv", "w") as file:
                    cur.copy_expert(export_query, file)