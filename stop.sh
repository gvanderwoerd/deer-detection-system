#!/bin/bash
# Deer Detection System Stop Script
# Stops the Flask server

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Stopping Deer Detection System...${NC}"

if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    PID=$(lsof -ti:5000)
    echo -e "${YELLOW}Killing server (PID: $PID)...${NC}"
    kill -9 $PID 2>/dev/null
    sleep 1

    if ! lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${GREEN}✓ Server stopped successfully${NC}"
    else
        echo -e "${RED}✗ Failed to stop server${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}No server running on port 5000${NC}"
fi
