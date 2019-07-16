import subprocess
import os

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
s3://{BucketName-(Data Lake)}/{InstanceName}/{DBName}/{TableName}.csv

"""

# This method allows me to connect to export csv files for each table. 
# This method does not require the maintenance of a JSON file at all, just different AWS credentials
# needed for different servers if different users have different access to the databases.

DATALAKE_NAME = 'hubble-datalake'


## Class Methods (Should encapsulate all s3 and rds methods to make the work easier to undestand) ----------------------------------
class S3Helper:
    def __init__(self):
        self.client = boto3.client("s3")
        self.s3 = boto3.resource('s3')

    def create_folder(self, path, location):
        """
        The idea of this function is to encapsulate all kinds of folder creation in s3
        1. Create bucket (if bucket does not exist)
        2. Create folders
        """
        path_arr = path.rstrip("/").split("/")
        # If the path given is only the bucket name.
        if len(path_arr) == 1:
            return _check_bucket(location)
        parent = path_arr[0]
        self._check_bucket(parent)
        bucket = self.s3.Bucket(parent)
        status = bucket.put_object(Key="/".join(path_arr[1:]) + "/")
        return status

    def upload(self, file, bucketname, pathname):
        self.s3.meta.client.upload_file(file, bucketname, pathname)

    def _check_bucket(self, location):
        # Check if data lake exists
        bucketlist = self.client.list_buckets()['Buckets']
        print (bucketlist)
        bucketnames = list(map(lambda x: x['Name'], bucketlist))
        print (bucketnames)
        datalake = list(filter(lambda x: x.lower() == DATALAKE_NAME, bucketnames))
        print (datalake)

        # We can create a datalake for each region as well, but for now we don't need to do that yet.
        # datalake_name = DATALAKE_NAME + "-" + location
        if not datalake:
            # Create a bucket based on given region
            self.client.create_bucket(Bucket = DATALAKE_NAME
        )
        return True

class RDSHelper():
    def __init__(self, *args, **kwargs):
        self.client = boto3.client("rds")

    def describe_db_instances(self, filters=None):
        if not filters:
            dbs = self.client.describe_db_instances()['DBInstances']
        else:
            dbs = self.client.describe_db_instances(Filters=filters)
        return dbs


# Actual Program -----------------------------------------------
def run(instance_filters=None):
    """
    instance_filters (dict): for now it can be anything we are going to use to filter the instance: 
    1. db-cluster-id 2. db-instance-id
    A filter name and value pair that is used to return a more specific list of results from a describe operation. 
    Filters can be used to match a set of resources by specific criteria, such as IDs.
    The filters supported by a describe operation are documented with the describe operation.
    E.g. [{"Name" :"tag:keyname", "Values":[""] }] - Must explicitly specify "Names" and "Values" pair. 

    """
    rds = RDSHelper()
    dbs = rds.describe_db_instances(filters=instance_filters)
    
    for db in dbs:
        instance = db['DBInstanceIdentifier']
        dbuser = db['MasterUsername']
        endpoint = db['Endpoint']
        host = endpoint['Address']
        port = endpoint['Port']
        location = str(db['DBInstanceArn'].split(':')[3])

        print('instance:', instance)
        print('dbuser:', dbuser)
        print('endpoint:', endpoint)
        print('host:', host)
        print('port:', port)
        print('location:', location)


        con = psycopg2.connect(dbname='postgres', host=host, port=port, user=dbuser)
        cur = con.cursor()

        def extract_name_query(title, qry):
            print('%s' % (title))
            cur.execute(qry)
            results = cur.fetchall()
            result_names = list(map(lambda x: x[0], results))
            return result_names
        
        # List all available databases in the same instance
        database_names = extract_name_query('listing databases', 'SELECT * FROM pg_database')
        print(database_names)

        for database_name in database_names:
            if database_name.lower() not in ['postgres', 'rdsadmin', 'template1', 'template0']:
                # Change database connection
                print("Accessing", database_name, "...")
                con = psycopg2.connect(dbname=database_name, host=host, port=port, user=dbuser)
                cur = con.cursor()

                # List all available tables in the same instance
                table_query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
                table_names = extract_name_query('listing tables', table_query)
                print(table_names)

                for table_name in table_names:
                    # Save individual tables to CSV first - as we are sending one table at a time, we can del the csv files 
                    # as soon as we have uploaded them
                    print("Accessing", table_name, "...")
                    export_query = "COPY " + table_name + " TO STDOUT WITH CSV HEADER"
                    csvname = table_name + ".csv"
                    with open(csvname, "w") as csvfile:
                        cur.copy_expert(export_query, csvfile)

                    folder_path = ("%s/%s/%s") % (DATALAKE_NAME, instance, database_name)

                    s3 = S3Helper()
                    s3.create_folder(folder_path, location)
                    table_path = ("%s/%s/%s.csv") % (instance, database_name, table_name)
                    s3_path = ("s3://%s/%s") % (DATALAKE_NAME, table_path)

                    #Upload the file to the respective bucket
                    s3.upload(csvname, DATALAKE_NAME, table_path)

                    print('FILE PUT AT:', s3_path)
                    
                    #Deleting file after use
                    os.remove(csvname)
                    print('File Deleted')



if __name__ == "__main__":
    run()

                
            