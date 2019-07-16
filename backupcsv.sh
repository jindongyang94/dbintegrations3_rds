#!/bin/sh

if [[ -z "${IDENTIFIER}" ]]; then
  echo "Missing environment variable IDENTIFIER"
  exit 1
fi
echo identifier: ${IDENTIFIER}

if [[ -z "${DATABASE_HOST}" ]]; then
  echo "Missing environment variable DATABASE_HOST"
  exit 1
fi
echo database-host:${DATABASE_HOST}

if [[ -z "${DATABASE_NAME}" ]]; then
  echo "Missing environment variable DATABASE_NAME"
  exit 1
fi
echo database-NAME:${DATABASE_NAME}

if [[ -z "${DATABASE_USER}" ]]; then
  echo "Missing environment variable DATABASE_USER"
  exit 1
fi
echo database-user:${DATABASE_USER}

if [[ -z "${S3_BUCKET}" ]]; then
  echo "Missing environment variable S3_BUCKET"
  exit 1
fi
echo s3-bucket:${S3_BUCKET}

psql\ 
-h companya.cxayn7ywcuuz.ap-southeast-1.rds.amazonaws.com \
-p 5432 \
-d companyaworkers \
-U jin -c \
"\copy workers from STDIN with delimiter as ','" | \
aws s3 cp --sse aws:kms - s3://mixedintegration/companya/companyaworkers/workers.csv

echo Done



psql-h companya.cxayn7ywcuuz.ap-southeast-1.rds.amazonaws.com \
-p 5432 \
-d companyaworkers \
-U jin \
--csv
-c "\copy workers from STDIN with delimiter as ','"\
 | aws s3 cp --sse aws:kms - s3://mixedintegration/companya/companyaworkers/workers.csv


