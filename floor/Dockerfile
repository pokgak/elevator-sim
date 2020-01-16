FROM python:alpine

# Add projekt source
WORKDIR /usr/src/floor
COPY . ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python", "FloorSimulator.py"]