#!/bin/bash

set -e

###########Config###########

#Number of Elevators
ELEVATOR=1

#Number of Floors
FLOORS=2


############################


DOCKERFILE=${PWD}/docker-compose.yml
DOCKER_TEMPLATE=${PWD}/build/docker-compose.yml
DOCKER_REPO=docker-hub.informatik.haw-hamburg.de/wp-cps
#############################

cat ${DOCKER_TEMPLATE} > ${DOCKERFILE}

for i in $(seq 1 $ELEVATOR); do
    let "IP = i + 4"
    echo "  elevator${i}:"  >> ${DOCKERFILE}
    echo "    build: ./elevator" >> ${DOCKERFILE}
    echo "    image: ${DOCKER_REPO}/elevator" >> ${DOCKERFILE}
    echo "    environment:" >> ${DOCKERFILE}
    echo "      - capacity=20" >> ${DOCKERFILE}
    echo "      - mqtt_host=mqtt" >> ${DOCKERFILE}
    echo "    depends_on:" >> ${DOCKERFILE}
    echo "      - mqtt" >> ${DOCKERFILE}
    echo "      - controller" >> ${DOCKERFILE}
    echo "    networks:" >> ${DOCKERFILE}
    echo "      cps_sim:" >> ${DOCKERFILE}
    echo "        ipv4_address: 172.21.0.${IP}" >> ${DOCKERFILE}
    echo "" >> ${DOCKERFILE}
done

# replaced by input-feeder
# for i in $(seq 1 $FLOORS); do
#     echo "  floor${i}:"  >> ${DOCKERFILE}
#     echo "    image: ${DOCKER_REPO}/FahrgastSimulator" >> ${DOCKERFILE}
#     echo "    environment:" >> ${DOCKERFILE}
#     echo "      - camera_floor=${i}" >> ${DOCKERFILE}
#     echo "      - mqtt_host=mqtt" >> ${DOCKERFILE}
#     echo "    depends_on:" >> ${DOCKERFILE}
#     echo "      - mqtt" >> ${DOCKERFILE}
#     echo "" >> ${DOCKERFILE}
# done