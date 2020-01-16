FROM python:alpine

# Add projekt source
WORKDIR /usr/src/input-feeder
# only copy requirements
COPY ./requirements.txt ./requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
# copy rest of files
COPY . .
COPY samples samples

RUN ["ls", "-alR", "samples"]
ENTRYPOINT ["python", "input_feeder.py", "-sample", "./samples/simple_scenario.json"]