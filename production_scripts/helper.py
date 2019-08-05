import subprocess
import os
import re
import csv
import contextlib
from datetime import datetime

import boto3
import psycopg2

"""
All the Helper Functions needed to run our scripts. We can put this as a lambda layer next time as well. 
"""

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

    def delete_csv(self, full_table_path):
        """
        Deleting any csv found possibly w a certain prefix as well.
        """
        path_arr = full_table_path.rstrip("/").split("/")
        bucket_name = path_arr[0]
        table_path = "/".join(path_arr[1:])
        bucket = self.s3.Bucket(bucket_name)
        response = bucket.delete_objects(
                Delete={
                    'Objects': [
                        {
                            'Key':  table_path
                        }
                    ]
                }
            )

        return response['Deleted'][0]['Key']

    def delete_all(self, full_folder_path):
        """
        Delete all csvs under a certain folder
        """
        path_arr = full_folder_path.rstrip("/").split("/")
        bucket_name = path_arr[0]
        folder_path = "/".join(path_arr[1:]) + '/'
        bucket = self.s3.Bucket(bucket_name)
        deleted_keys = []

        for key in bucket.objects.filter(Prefix=folder_path):
            keyname = key.key
            print('Keyname: %s' % keyname)
            # Only delete csvs
            if keyname.split(".")[-1] == 'csv':
                response = bucket.delete_objects(
                    Delete={
                        'Objects': [
                            {
                                'Key':  keyname
                            }
                        ]
                    }
                )
                deleted_keys.append(response['Deleted'][0]['Key'])

        return deleted_keys


    def download_latest(self, full_folder_path):
        """
        Return csv filename with the latest timestamp from the folder path
        """
        path_arr = full_folder_path.rstrip("/").split("/")
        bucket_name = path_arr[0]
        folder_path = "/".join(path_arr[1:]) + '/'

        with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
            timestamp = self.latest_s3timestamp(full_folder_path)
            csvtimestamp = self._convert_s3timestamp(timestamp)

        if timestamp:
            selected_key = None
            bucket = self.s3.Bucket(bucket_name)
            for key in bucket.objects.filter(Prefix=folder_path):
                if re.search(csvtimestamp, key.key):
                    selected_key = key.key
                    break
            
            print ("Selected CSV: ", selected_key)
            # if you cannot find the selected key at this point, something with the code / bucket is terribly wrong.
            if not selected_key:
                raise ValueError('The selected timestamp (%s) could not be found. Please check code or s3 bucket.' % timestamp)
            
            keyname = selected_key.split('/')[-1]
            local_keypath = '/tmp/' + keyname
            bucket.download_file(selected_key, local_keypath)

            print ("Local CSV File:", local_keypath)

            # Delete the file from s3 as we do not need it anymore.
            response = bucket.delete_objects(
                Delete={
                    'Objects': [
                        {
                            'Key':  selected_key
                        }
                    ]
                }
            )
            print ("Deleted object from s3:", response['Deleted'][0]['Key'])

            return local_keypath
        
        return None

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
        print ("Folder Path: ", folder_path)
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
            print('File: %s' % filename)

            # Split to remove filename - Assuming '-' can separate name from timestamp
            # We store and update the timestamps differently - remove all ' ', '-', '_', '.', '+'
            # When converting it back to a timestamp, we can use the positions to do so, as that will never change in a timestamp.
            # E.g. 2019-07-07 20:46:14.694288+10:00 --> 201907072046146942881000
            try:
                timestamp = str(filename.split('-')[-1])
                if not re.search("^[0-9]{24}$", timestamp):
                    # print ('This is not a valid timestamp: %s' % timestamp)
                    continue
            except (TypeError, ValueError):
                continue
            print ('Found valid timestamp: %s' % timestamp)
            timestamps.append(timestamp)
        
        print ('Timestamp List: %s \n' % timestamps)

        # Filter for the latest timestamp (biggest value)
        try:
            latest = max(timestamps)
            # Format the value back to timestamp needed in postgres
            latest = self._convert_timestamp(latest)
            print ("Found Latest Timestamp in S3: ", latest)

        except ValueError:
            # If no timestamp exist, return None
            latest = None

        return latest
    
    def _check_bucket(self, location):
        # Check if data lake exists
        bucketlist = self.client.list_buckets()['Buckets']
        # print(bucketlist)
        bucketnames = list(map(lambda x: x['Name'], bucketlist))
        # print(bucketnames)
        datalake = list(filter(lambda x: x.lower() ==
                               DATALAKE_NAME, bucketnames))
        # print(datalake)

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
        E.g. 2019070720461469428810 --> 2019-07-07 20:46:14.694288+10:00
        """
        result = value[:4] + '-' + value[4:6] + '-' + value[6:8] + ' ' + value[8:10] + ':' \
            + value[10:12] + ':' + value [12:14] + '.' \
                + value[14:20] + '+' + value[20:22] + ':' + value[22:]
        return result

    def _convert_s3timestamp(self, value):
        """
        Convert and remove to only 24 digits
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

class PGHelper():
    def __init__(self, db, host, port, dbuser):
        # get the password if there is such a thing
        self.db = db
        self.password = os.environ.get('PG_PASS')
        self.host = host
        self.port = port
        self.dbuser = dbuser
    
    def conn(self, database=None):
        """
        Connect with or without password depending on PG PASS evironment variable.
        """
        if database:
            self.db = database

        if self.password:
            # print('Password:', self.password)
            con = psycopg2.connect(
                dbname=self.db, host=self.host, port=self.port, user=self.dbuser, password=self.password)
        else:
            con = psycopg2.connect(
                dbname=self.db, host=self.host, port=self.port, user=self.dbuser)

        return con