FROM python:alpine

# Install dependencies
COPY ./recorder/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# build and install the cps_common package
COPY ./common /app/common
WORKDIR /app/common
RUN python3 setup.py sdist bdist_wheel && pip3 install .

WORKDIR /app/recorder
# Add projekt source
COPY ./recorder ./

ENTRYPOINT ["python", "recorder.py", "-resdir", "/app/recorder/data/logs"]
