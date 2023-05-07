#/bin/bash

docker exec home-monitor-db-mon-1 pg_dump -d postgres -U postgres -f /backup/postgres-db.sql

