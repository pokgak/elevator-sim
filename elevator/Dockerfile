FROM python:alpine

WORKDIR /app

# Install dependencies
COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Add projekt source
COPY ./ ./

ENTRYPOINT ["python", "elevator.py", "-log", "info"]
