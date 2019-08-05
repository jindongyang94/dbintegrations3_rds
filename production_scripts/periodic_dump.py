import subprocess
import os
import re
import csv
import contextlib
from datetime import datetime

import boto3
import psycopg2

from helper import RDSHelper, PGHelper, S3Helper, DATALAKE_NAME

"""
The idea of this script is a simplified version of a daily migration script, refreshing the s3 lake for a specific duration. 

"""

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

    print ("Instances List:", list(map(lambda x: x['DBInstanceIdentifier'], dbs)))

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

        print ("\nAccessing instance %s ..." % instance)

        pg = PGHelper(db='postgres', host=host, port=port, dbuser=dbuser)
        con = pg.conn()
        cur = con.cursor()

        def extract_name_query(title, qry):
            print('%s' % (title))
            cur.execute(qry)
            results = cur.fetchall()
            result_names = list(map(lambda x: x[0], results))
            return result_names

        # List all available databases in the same instance
        database_names = extract_name_query(
            'Extracting databases...', 'SELECT * FROM pg_database')

        # Filtering available databases
        default_databases = ['postgres', 'rdsadmin', 'template1', 'template0']
        database_names = list(
            filter(lambda x: x not in default_databases, database_names))
        if database_filters:
            database_names = list(
                filter(lambda x: x in database_filters, database_names))
        
        print("Databases List:", database_names)

        for database_name in database_names:
            # Change database connection
            print("\nAccessing", database_name, "...")
            con = pg.conn(database=database_name)
            cur = con.cursor()

            # List all available tables in the same instance
            table_query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
            table_names = extract_name_query('Extracting tables...', table_query)

            # Filtering available tables
            if table_filters:
                table_names = list(
                    filter(lambda x: x in table_names, table_names))
            
            print("Tables List:", table_names)

            for table_name in table_names:
                # Save individual tables to CSV first - as we are sending one table at a time, we can del the csv files
                # as soon as we have uploaded them
                print("\nAccessing", table_name, "...")
                # We will save the time based on the latest commit time. Thus, there will be only one file for one table all time
                # However, they might be of different timestamp due to difference in commit time.

                s3 = S3Helper()
                # Extract latest timestamp separately here:
                # Use this query to extract the latest commit timestamp at that point of time
                extract_ts_query = "SELECT MAX(pg_xact_commit_timestamp(xmin)) FROM " + table_name + " WHERE pg_xact_commit_timestamp(xmin) IS NOT NULL;"
                cur.execute(extract_ts_query)
                latest_timestamp = str(cur.fetchone()[0])

                # Define needed timestamp to set the csvname we are using.
                if latest_timestamp:
                    print ("Latest Commit Timestamp from PostGres is: %s" % latest_timestamp)
                    latest_csvtimestamp = s3._convert_s3timestamp(latest_timestamp)
                
                # However, if there is no timestamp at all, then use 24 '0's as the default. 
                else:
                    print ("No Commit Timestamp available in PostGres. Using default.")
                    latest_csvtimestamp = '0' * 24
                
                csvname = table_name + "-" + latest_csvtimestamp + ".csv"

                # Respective paths needed
                full_folder_path = ("%s/%s/%s") % (DATALAKE_NAME, instance, database_name)
                table_path = ("%s/%s/%s") % (instance, database_name, csvname)
                full_table_path = "%s/%s/%s/%s" % (DATALAKE_NAME, instance, database_name, csvname)
                s3_path = ("s3://%s/%s") % (DATALAKE_NAME, table_path)

                # Grab the latest_timestamp from the folder. Ideally, there should only be one file under each table folder, but
                # we will still segregate them as such for easy referencing.
                table_timestamp = s3.latest_s3timestamp(full_folder_path)

                # If we could not get a proper timestamp from s3, it means there is no initial file. 
                if not table_timestamp:
                    print ("There is no need to delete any existing CSVs. Proceed to export table %s to csv." %  table_name)
                else:
                    print ("CSV File found with Commit Timestamp: %s. Proceed to delete it." % table_timestamp)
                    # Even when the same timestamp is found, the script should still do an indiscriminate dumping.
                    # Delete the files with the timestamp and then do the same dumping.

                    # Option 1 - Delete only the csv file we want.
                    # table_csvtimestamp = s3._convert_s3timestamp(table_timestamp)
                    # s3csvpath = table_name + '-' + table_csvtimestamp + '.csv'
                    # fullcsvpath = full_folder_path + '/' + s3csvpath
                    # csvs = s3.delete_csv(fullcsvpath)

                    # Option 2 - Delete every csv under the folderpath
                    csvs = s3.delete_all(full_folder_path)
                    print ("CSV File '%s' deleted. Proceed to export table %s to csv." %  (csvs, table_name))
                
                local_csvpath = '/tmp/' + csvname
                with open(local_csvpath, "w") as csvfile:
                    # Get all of the rows and export them
                    export_query = "COPY " + table_name + " TO STDOUT WITH CSV HEADER"
                    cur.copy_expert(export_query, csvfile)

                # Upload the file to the respective bucket - Replacing or uploading uses the same function
                # This way of uploading would not resetting the entire path, so it is fine to not add a check.
                s3.create_folder(full_folder_path, location)
                s3.upload(local_csvpath, full_table_path)
                latest_timestamp = s3._convert_timestamp(latest_csvtimestamp)
                print ('FILE PUT AT: %s with Latest Committed Time (%s)' % (s3_path, latest_timestamp))

                # Deleting file from /tmp/ after use
                os.remove(local_csvpath)
                print ('Local File Deleted\n')


def handler(event, context):
    # The tag or name of the instance we want to enter
    # instance_tags = {}

    # The given companies
    # correct_databases = [
    # ]

    # The related modules needed
    # correct_tables = []

    run(instance_filters=None, database_filters=None)


if __name__ == "__main__":
    event = None
    context = None
    handler(event, context)
