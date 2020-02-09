# Simulation

## Building code

- Update build code and run in background: `docker-compose up --build --remove-orphans -d`
- Start gui: `cd gui; python3 dashboard.py`
- Send input to floors: `cd input-feeder; python3 input_feeder.py -samples samples/one_at_a_time.yaml`
