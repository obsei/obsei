#!/bin/bash

# Stop the RQ worker process
pkill -f "rq worker"

# Wait for a few seconds
sleep 5

# Start the RQ worker process again
nohup rq worker &>/dev/null &
