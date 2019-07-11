import os
import json
import subprocess

"""
The idea of this file is to create and update the environment variables iteratively, and the 
script can be used to run the bash file found online. 

The environment variables would be put together based on what is written in the json. 

"""

with open("info.json", "r") as credentials:
    creds = json.load(credentials)

for key, value in creds.items():
    os.environ['IDENTIFIER'] = key
    os.environ['DATABASE_HOST'] = value['database-host']
    os.environ['DATABASE_USER'] = value['database-user']
    os.environ['DATABASE_NAME'] = value['database-name']
    os.environ['S3_BUCKET'] = value['s3-bucket']

    subprocess.call(['/Users/peter/temp_docs/dbintegration/backup.sh'])



