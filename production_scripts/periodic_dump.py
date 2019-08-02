import subprocess
import os
import re

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

Since tables will never be able to be appended directly from s3, it does not make sense to load the entire csv all the time. 
Perhaps write another script to merge each csvs based on time periodically. 

S3 files would be named as follows: 
s3://{BucketName-(Data Lake)}/{InstanceName}/{DBName}/{TableName}/{TableName-TimeStamp}.csv

"""

# This method allows me to connect to export csv files for each table.
# This method does not require the maintenance of a JSON file at all, just different AWS credentials
# needed for different servers if different users have different access to the databases.

DATALAKE_NAME = 'hubble-datalake'


# Class Methods (Should encapsulate all s3 and rds methods to make the work easier to undestand) ----------------------------------
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
            return self._check_bucket(location)
        parent = path_arr[0]
        self._check_bucket(parent)
        bucket = self.s3.Bucket(parent)
        status = bucket.put_object(Key="/".join(path_arr[1:]) + "/")
        return status

    def upload(self, file, full_table_path):
        """
        Take the file, and upload to the bucketname to the specific path (pathname without bucketname)
        """
        path_arr = full_table_path.rstrip("/").split("/")
        bucketname = path_arr[0]
        table_path = "/".join(path_arr[1:])
        self.s3.meta.client.upload_file(file, bucketname, table_path)

    def download(self, full_folder_path):
        """
        Return latest csv filename in the folder path
        """
        path_arr = full_folder_path.rstrip("/").split("/")
        bucket_name = path_arr[0]
        folder_path = "/".join(path_arr[1:]) + '/'

        timestamp = self.latest_s3timestamp(full_folder_path)

        if timestamp:
            selected_key = None
            bucket = self.s3.Bucket(bucket_name)
            for key in bucket.objects.filter(Prefix=folder_path):
                if re.search(timestamp, key.key):
                    selected_key = key.key
                    break
            
            # if you cannot find the selected key at this point, something with the code / bucket is terribly wrong.
            if not selected_key:
                conv_timestamp = self._convert_timestamp(timestamp)
                raise ValueError('The selected timestamp (%s) could not be found. Please check code or s3 bucket.' % conv_timestamp)
            
            key_path = folder_path + selected_key
            local_keypath = '/tmp/' + key_path
            self.client.download_file(bucket_name, key_path, local_keypath)
            return local_keypath

    def latest_s3timestamp(self, full_folder_path):
        """
        Check the path and see if there is any file.
        If there is, grab the latest timestamp on the file. 
        """
        empty = self._check_empty(full_folder_path)
        if empty:
            return None

        path_arr = full_folder_path.rstrip("/").split("/")
        bucket_name = path_arr[0]
        folder_path = "/".join(path_arr[1:]) + '/'
        bucket = self.s3.Bucket(bucket_name)
        timestamps = []

        for key in bucket.objects.filter(Prefix=folder_path):
            keyname = key.key
            # Split to each directories
            keyname = keyname.split("/")
            print('Keyname: %s' % keyname)
            # Don't touch any folders within the folders we specified
            if keyname[-1] == '':
                continue
            filename = str(keyname[-1])
            # Split to remove the extension path
            filename = str(filename.split('.')[0])
            print('Filename: %s' % filename)

            # Split to remove filename - Assuming '-' can separate name from timestamp
            # We store and update the timestamps differently - remove all ' ', '-', '_', '.', '+'
            # When converting it back to a timestamp, we can use the positions to do so, as that will never change in a timestamp.
            # E.g. 2019-07-07 20:46:14.694288+10 --> 2019070720461469428810
            try:
                timestamp = int(filename.split('-')[-1])
                if re.search("^[0-9]{22}$", timestamp):
                    print ('This is not a valid timestamp: %s' % timestamp)
                    continue
            except (TypeError, ValueError):
                continue
            timestamps.append(timestamp)
        
        print ('Timestamp List: %s' % timestamps)

        # Filter for the latest timestamp (biggest value)
        try:
            latest = str(max(timestamps))

            # Format the value back to timestamp needed in postgres
            latest = self._convert_timestamp(latest)

        except ValueError:
            # If no timestamp exist, return None
            latest = None

        return latest
    
    def _check_bucket(self, location):
        # Check if data lake exists
        bucketlist = self.client.list_buckets()['Buckets']
        print(bucketlist)
        bucketnames = list(map(lambda x: x['Name'], bucketlist))
        print(bucketnames)
        datalake = list(filter(lambda x: x.lower() ==
                               DATALAKE_NAME, bucketnames))
        print(datalake)

        # We can create a datalake for each region as well, but for now we don't need to do that yet.
        # datalake_name = DATALAKE_NAME + "-" + location
        if not datalake:
            # Create a bucket based on given region
            self.client.create_bucket(Bucket=DATALAKE_NAME)
        return True

    def _check_empty(self, path_arr):
        """
        This function will check in the folder is empty in s3
        """
        path_arr = path_arr.rstrip("/").split("/")
        bucket_name = path_arr[0]
        folder_path = "/".join(path_arr[1:]) + '/'
        bucket = self.s3.Bucket(bucket_name)

        if bucket.objects.filter(Prefix=folder_path):
            return False
        return True

    def _convert_timestamp(self, value):
        """
        Convert the value back to postgres timestamp format
        E.g. 2019070720461469428810 --> 2019-07-07 20:46:14.694288+10 
        """
        result = value[:4] + '-' + value[4:6] + '-' + value[6:8] + ' ' + value[8:10] + ':' 
        + value[10:12] + ':' + value [12:14] + '.' + value[14:20] + '+' + value[20:]
        return result

    def _convert_s3timestamp(self, value):
        """
        Convert and remove to only 22 digits
        E.g. 
        """
        result = re.sub("[^\\d]", "", value)
        return result

class RDSHelper():
    def __init__(self, *args, **kwargs):
        self.client = boto3.client("rds")

    def describe_db_instances(self, filters=None):
        if not filters:
            dbs = self.client.describe_db_instances()['DBInstances']
        else:
            dbs = self.client.describe_db_instances(Filters=filters)[
                'DBInstances']
        return dbs


# Actual Program -----------------------------------------------
def run(instance_filters=None, database_filters=None, table_filters=None):
    """
    -instance_filters (dict): for now it can be anything we are going to use to filter the instance: 
    1. db-cluster-id 2. db-instance-id
    A filter name and value pair that is used to return a more specific list of results from a describe operation. 
    Filters can be used to match a set of resources by specific criteria, such as IDs.
    The filters supported by a describe operation are documented with the describe operation.
    E.g. [{"Name" :"tag:keyname", "Values":[""] }] - Must explicitly specify "Names" and "Values" pair. 

    -database_filters (list): simply only append the database names to this list so we only access those databases. By default,
    it will access all

    -table_filters (list): simply only append table names to this list so we only export those tables. By default it will export all. 

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

        con = psycopg2.connect(
            dbname='postgres', host=host, port=port, user=dbuser)
        cur = con.cursor()

        def extract_name_query(title, qry):
            print('%s' % (title))
            cur.execute(qry)
            results = cur.fetchall()
            result_names = list(map(lambda x: x[0], results))
            return result_names

        # List all available databases in the same instance
        database_names = extract_name_query(
            'listing databases', 'SELECT * FROM pg_database')
        print(database_names)

        # Filtering available databases
        default_databases = ['postgres', 'rdsadmin', 'template1', 'template0']
        database_names = list(
            filter(lambda x: x not in default_databases, database_names))
        if database_filters:
            database_names = list(
                filter(lambda x: x in database_filters, database_names))

        for database_name in database_names:
            # Change database connection
            print("Accessing", database_name, "...")
            con = psycopg2.connect(dbname=database_name,
                                   host=host, port=port, user=dbuser)
            cur = con.cursor()

            # List all available tables in the same instance
            table_query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
            table_names = extract_name_query('listing tables', table_query)
            print(table_names)

            # Filtering available tables
            if table_filters:
                table_names = list(
                    filter(lambda x: x in table_names, table_names))

            for table_name in table_names:
                # Save individual tables to CSV first - as we are sending one table at a time, we can del the csv files
                # as soon as we have uploaded them
                print("Accessing", table_name, "...")
                

                # We will save the time based on the latest commit time. Thus, there will be only one file for one table all time
                # However, they might be of different timestamp due to difference in commit time.

                full_folder_path = ("%s/%s/%s") % (DATALAKE_NAME, instance, database_name)
                table_path = ("%s/%s/%s") % (instance, database_name, csvname)
                full_table_path = "%s/%s/%s/%s" % (DATALAKE_NAME, instance, database_name, csvname)
                s3_path = ("s3://%s/%s") % (DATALAKE_NAME, table_path)

                s3 = S3Helper()
                # Grab the latest_timestamp from the folder. Ideally, there should only be one file under each table folder, but
                # we will still segregate them as such for easy referencing.
                table_timestamp = s3.latest_s3timestamp(full_table_path)

                # if there is a csv file with table timestamp, we should delete it
                if table_timestamp:
                    pass

                # Get all of the rows, with the latest timestamp as the latest committed timestamp.
                export_query = "COPY " + table_name + " TO STDOUT WITH CSV HEADER"

                # Extract latest timestamp separately here:
                # Use this query to extract the latest commit timestamp at that point of time
                extract_ts_query = "SELECT MAX(pg_xact_commit_timestamp(xmin)) FROM " + table_name + " WHERE pg_xact_commit_timestamp(xmin) IS NOT NULL;"
                cur.execute(extract_ts_query)
                latest_timestamp = cur.fetchone()

                if latest_timestamp:
                    latest_csvtimestamp = s3._convert_s3timestamp(latest_timestamp)
                    csvname = table_name + "-" + latest_csvtimestamp + ".csv"
                else:
                    # However, if there is no timestamp at all, then use 22 '0's as the default. 
                    default_csvtimestamp = '0' * 22
                    csvname = table_name + "-" + default_csvtimestamp + ".csv"

                # Indiscriminate dump which replaces the original csv
                local_csvpath = '/tmp/' + csvname
                with open(local_csvpath, "w") as csvfile:
                    cur.copy_expert(export_query, csvfile)

                # Upload the file to the respective bucket
                # This way of uploading would not reseting the entire path, so it is fine to not add a check.
                s3.create_folder(full_folder_path, location)
                s3.upload(local_csvpath, full_table_path)

                print('FILE PUT AT:', s3_path)

                # Deleting file after use
                os.remove(local_csvpath)
                print('File Deleted')
            



if __name__ == "__main__":
    # The tag or name of the instance we want to enter
    instance_tags = {}

    # The given companies
    correct_databases = [
        "alric",
        "hsc",
        "bms",
        "cleansolution",
        "lumchang",
        "firstcom",
        "multiscaff",
        "sante",
        "tongloong",
        "oas",
        "sck",
        "kkl",
        "primestructures",
        "hexacon",
        "hitek",
        "wohhup",
        "keppelshipyard",
        "greatearth",
        "seiko",
        "weehur",
        "boustead"
    ]

    # The related modules needed
    # correct_tables = []

    run(instance_filters=None, database_filters=None)
