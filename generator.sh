#!/bin/bash

set -e

###########Config###########

#Number of Elevators
ELEVATOR=6

#Number of Floors
FLOORS=11


############################


DOCKERFILE=${PWD}/docker-compose.yml
DOCKER_TEMPLATE=${PWD}/build/docker-compose.yml
DOCKER_REPO=docker-hub.informatik.haw-hamburg.de/wp-cps
#############################

cat ${DOCKER_TEMPLATE} > ${DOCKERFILE}

for i in $(seq 1 $ELEVATOR); do
    echo "  elevator${i}:"  >> ${DOCKERFILE}
    echo "    image: ${DOCKER_REPO}/elevator" >> ${DOCKERFILE}
    echo "    environment:" >> ${DOCKERFILE}
    echo "      - capacity=20" >> ${DOCKERFILE}
    echo "      - mqtt_host=mqtt" >> ${DOCKERFILE}
    echo "    depends_on:" >> ${DOCKERFILE}
    echo "      - mqtt" >> ${DOCKERFILE}
    echo "" >> ${DOCKERFILE}
done

for i in $(seq 1 $FLOORS); do
    echo "  floor${i}:"  >> ${DOCKERFILE}
    echo "    image: ${DOCKER_REPO}/FahrgastSimulator" >> ${DOCKERFILE}
    echo "    environment:" >> ${DOCKERFILE}
    echo "      - camera_floor=${i}" >> ${DOCKERFILE}
    echo "      - mqtt_host=mqtt" >> ${DOCKERFILE}
    echo "    depends_on:" >> ${DOCKERFILE}
    echo "      - mqtt" >> ${DOCKERFILE}
    echo "" >> ${DOCKERFILE}
done