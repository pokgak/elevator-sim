FROM python:alpine

# Add projekt source
WORKDIR /usr/src/elevator_controller
COPY . ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python", "elevator_controller.py", "-log", "info"]