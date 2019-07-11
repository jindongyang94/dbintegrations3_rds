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


# DATE=$(date "+%Y-%m-%d") we should only use this function once we decided to version / timestamp our update
TARGET=s3://${S3_BUCKET}/${IDENTIFIER}/${DATABASE_NAME}.sql

echo Backing up ${DATABASE_HOST}/${DATABASE_NAME} to ${TARGET}

pg_dump -v -h ${DATABASE_HOST} -U ${DATABASE_USER} -d ${DATABASE_NAME} | aws s3 cp --sse aws:kms - ${TARGET}
rc=$?

if [[ $rc != 0 ]]; then exit $rc; fi

echo Done