FROM python:3.6

ADD requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

ADD workflow-schema.json /workflow-schema.json
ADD templates /templates
ADD static /static
ADD odatestsapp.py /app.py
ADD odarun.py /odarun.py
ADD odaworkflow.py /odaworkflow.py
ADD odaworker.py /odaworker.py

RUN pip install oda-api --upgrade

ENTRYPOINT gunicorn app:app -b 0.0.0.0:8000 --log-level INFO
