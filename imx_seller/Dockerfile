# you can build the image with:
#
#   docker build . -t paywall

FROM python:3.7 as builder

COPY . /app

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app/

RUN pip install -r requirements.txt

EXPOSE 5001

ENTRYPOINT ["/opt/venv/bin/python3", "paywall.py"]
