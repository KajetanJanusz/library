#!/bin/bash
docker compose -f docker-compose-local.yml down
docker system prune -a -f
docker volume rm $(docker volume ls -q)