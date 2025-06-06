FROM python:3.12

RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod 777 ./docker_entrypoint.sh

ENTRYPOINT [ "./docker_entrypoint.sh" ]