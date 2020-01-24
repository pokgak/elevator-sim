#!/bin/bash

set -e

###########Config###########

#Number of Elevators
ELEVATOR=1

#Number of Floors
FLOORS=4


############################


DOCKERFILE=${PWD}/docker-compose.yml
DOCKER_TEMPLATE=${PWD}/build/docker-compose.yml
DOCKER_REPO=docker-hub.informatik.haw-hamburg.de/wp-cps/simulation
#############################

cat ${DOCKER_TEMPLATE} > ${DOCKERFILE}

echo "  controller:" >> ${DOCKERFILE}
echo "      build: ./elevatorcontroller" >> ${DOCKERFILE}
echo "      image: docker-hub.informatik.haw-hamburg.de/wp-cps/simulation/controller" >> ${DOCKERFILE}
echo "      restart: always" >> ${DOCKERFILE}
echo "      depends_on:" >> ${DOCKERFILE}
echo "        - mqtt" >> ${DOCKERFILE}
echo "      environment:" >> ${DOCKERFILE}
echo "        - mqtt_host=mqtt" >> ${DOCKERFILE}
echo "        - floor_count=${FLOORS}" >> ${DOCKERFILE}
echo "        - elevator_count=${ELEVATOR}" >> ${DOCKERFILE}
echo "      networks:" >> ${DOCKERFILE}
echo "        cps_sim:" >> ${DOCKERFILE}
echo "          ipv4_address: 172.21.0.20" >> ${DOCKERFILE}
echo "" >> ${DOCKERFILE}

for i in $(seq 1 $ELEVATOR); do
    # IP 2-4 reserved for broker, controller
    let "IP = i + 10"

    echo "  elevator${i}:"  >> ${DOCKERFILE}
    echo "    container_name: elevator${i}" >> ${DOCKERFILE}
    echo "    build: ./elevator" >> ${DOCKERFILE}
    echo "    image: ${DOCKER_REPO}/elevator" >> ${DOCKERFILE}
    echo "    restart: always" >> ${DOCKERFILE}
    echo "    environment:" >> ${DOCKERFILE}
    echo "      - capacity=20" >> ${DOCKERFILE}
    echo "      - mqtt_host=mqtt" >> ${DOCKERFILE}
    echo "      - elevator_id=${i}" >> ${DOCKERFILE}
    echo "    depends_on:" >> ${DOCKERFILE}
    echo "      - mqtt" >> ${DOCKERFILE}
    echo "      - controller" >> ${DOCKERFILE}
    echo "    networks:" >> ${DOCKERFILE}
    echo "      - cps_sim" >> ${DOCKERFILE}
    echo "" >> ${DOCKERFILE}
done

MAX_FLOOR=$(($FLOORS - 1))
for i in $(seq 0 $MAX_FLOOR); do
    let "IP = IP + 1"

    echo "  floor${i}:"  >> ${DOCKERFILE}
    echo "    container_name: floor${i}" >> ${DOCKERFILE}
    echo "    build: ./floor" >> ${DOCKERFILE}
    echo "    image: ${DOCKER_REPO}/floor" >> ${DOCKERFILE}
    echo "    environment:" >> ${DOCKERFILE}
    echo "      - mqtt_host=mqtt" >> ${DOCKERFILE}
    echo "      - floor_level=${i}" >> ${DOCKERFILE}
    echo "    depends_on:" >> ${DOCKERFILE}
    echo "      - mqtt" >> ${DOCKERFILE}
    echo "      - controller" >> ${DOCKERFILE}
    echo "    networks:" >> ${DOCKERFILE}
    echo "      - cps_sim" >> ${DOCKERFILE}
    echo "" >> ${DOCKERFILE}
done
