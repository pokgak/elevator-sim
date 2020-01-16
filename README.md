# Simulation

docker-compose file and configs to create a simulation

All the separate services under the same repository for easier management.
The services are set to have static IP addresses for easier debugging with
Wireshark.

- MQTT Broker (172.21.0.2)
- Elevator Controller (172.21.0.3)
- Input Feeder (172.21.0.4)
- Elevator (172.21.0.5+)

The services have their own Dockerfile. Use `docker-compose build` and
`docker-compose push` to build and push all services.
