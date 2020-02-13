FROM python:alpine

# Install dependencies
COPY ./floor/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# build and install the cps_common package
COPY ./common /app/common
WORKDIR /app/common
RUN python3 setup.py sdist bdist_wheel && pip3 install .

# copy app files
WORKDIR /app/floor
# Add projekt source
COPY ./floor ./

ENTRYPOINT ["python", "floor.py"]
