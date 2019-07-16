FROM alpine:3.7
RUN apk --update add postgresql-client python py-pip
RUN rm -rf /var/cache/apk/*
RUN pip install --upgrade awscli
RUN pip install -r requirements.txt

WORKDIR /src
COPY backup.sh /src
COPY integration.py /src
RUN chmod +x /src/backup.sh

CMD /src/integration.py