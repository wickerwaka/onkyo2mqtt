FROM python:3.7-alpine

ENV MQTT_HOST=localhost
ENV MQTT_PORT=1883
ENV MQTT_TOPIC=onkyo/
ENV LOG=WARNING

RUN apk update && apk add python3-dev \
                          gcc \
                          libc-dev \
                          linux-headers

COPY requirements.txt /
RUN pip install -r /requirements.txt
COPY onkyo2mqtt.py /app/
WORKDIR /app
CMD python onkyo2mqtt.py \
    --mqtt-host=$MQTT_HOST \
    --mqtt-port=$MQTT_PORT \
    --mqtt-topic=$MQTT_TOPIC \
    --onkyo-address=$ONKYO_ADDRESS \
    --log=$LOG
