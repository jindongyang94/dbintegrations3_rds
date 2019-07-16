# multi rds-s3-database-copy
This script can also be done locally as well. 

<p>
<b>Method 1: (integration.py) - Backup</b>
</p>
<p>
You can run more than just one database connection at once using the same sh file by iterating through the json file. However, this can only be used to dump .sql files for backup. <br \>
However, please do the following as well (especially if you are running this locally):
</p>

<ol>
<li> Environment Configured for the AWS User  <br \>
./aws/config and ./aws/credentials - configure them the same as AWS website asked you.  <br \>
Ensure that you have the correct permissions tagged to this user as well, primarily S3 and RDS access. </li>

<li> Postgres password file to bypass the need to keep on entering passwords  <br \>
~/.pgpass → chmod 600  <br \>
Format: hostname:port:database:username:password  <br \>
https://www.postgresql.org/docs/10/libpq-pgpass.html  <br \>
If the username and password are going to be the same for all databases/host, you can simply put *:*:*:username:password <br \>

If you are doing this on Lambda or EC2 instance, database and user credentials can be retrieved from the aws parameter store. </li>

<li> Maintain the JSON file as per given in the example.json: Change the values with 'fake' in its name. </li>
</ol>

<p>
After that you can simply run the python file to run the shell script.
</p>

<p>
<b>Method 2: (integration2.py) - Export</b>
</p>
<p>
I have created another way using Boto3 and Psycopg2, which now does not require you to utilize a JSON file to maintain the host/ port/ user etc. However, you do have to perform the same configurations as stated above. This method also allows you to export the database to as a CSV file. You can change it however, if you want it to dump a .sql file as above as well. However, there are additional requirements due to the usage of python modules:
</p>

<ol>
<li> Please install Boto3 and Psycopg2 as per instructed in the requirements.txt using pip install -r requirements.txt </li>
</ol>

-------------------------------------------------------------------------------------------------------------------------------------------------------------------
The dockerfile now satisfy both requirements so you can use that to spin the container needed for both scripts. Both methods can be used interchangeably for your best results. For example, you can still use method 2 so you do not have to maintain a JSON file, but at the same time you can use the shell script in method 1 to back up as a .sql file. However, you will to write your own commmand to change the environment variables and run the shell script.

<b> Method 2 is always recommended as it does not require you to maintain a list at all, but at the same time still give you flexibility to configure / filter to whatever instances/databases/ tables you want to transfer to s3 respectively. </b>

<b>FUTURE CONSIDERATIONS:</b>

<ol>
<li> Possibly add more configuration options to allow better filtering etc.
</ol>
