FROM python:3.11-alpine
RUN apk add --no-cache mosquitto-clients
WORKDIR /app
COPY inverter_mqtt.py /app/
CMD ["python3", "-u", "/app/inverter_mqtt.py"]