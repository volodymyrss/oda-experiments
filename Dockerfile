FROM python:3.8

ADD requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

ADD workflow-schema.json /workflow-schema.json

ADD odaexperiments/templates /templates
#ADD static /static

ADD odaexperiments /odaexperiments
#ADD odaexperiments/app.py /app.py
#ADD odarun.py /odarun.py
#ADD odaworkflow.py /odaworkflow.py
#ADD odaworker.py /odaworker.py

ENV PYTHONPATH=/
ENV XDG_CACHE_HOME=/tmp
ENV MPLCONFIGDIR=/tmp

RUN adduser oda
USER oda

ENTRYPOINT gunicorn odaexperiments.app:app -b 0.0.0.0:8000 -w 8 --log-level DEBUG --timeout 600
