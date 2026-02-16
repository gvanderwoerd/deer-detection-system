#!/bin/bash
# Deer Detection System Startup Script
# Starts the Flask server and opens the web dashboard

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🦌 Starting Deer Detection System...${NC}"

# Check if server is already running
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    EXISTING_PIDS=$(lsof -ti:5000)
    echo -e "${YELLOW}⚠️  Server already running on port 5000 (PID: $EXISTING_PIDS)${NC}"
    read -p "Kill existing server and restart? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Stopping existing server(s)...${NC}"
        lsof -ti:5000 | xargs kill -9 2>/dev/null || true
        sleep 2
        # Verify all instances are stopped
        if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
            echo -e "${RED}✗ Failed to stop server${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ All existing instances stopped${NC}"
    else
        echo -e "${GREEN}Opening dashboard in existing server...${NC}"
        xdg-open http://192.168.1.15:5000 &
        exit 0
    fi
fi

# Navigate to server directory
cd "$(dirname "$0")/server"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update requirements
echo -e "${YELLOW}Checking dependencies...${NC}"
pip install -q -r requirements.txt

# Check for required files
if [ ! -f "yolov8n.pt" ]; then
    echo -e "${RED}⚠️  Warning: yolov8n.pt model file not found${NC}"
    echo -e "${YELLOW}The detection system will download it on first run${NC}"
fi

if [ ! -f "tinytuya.json" ]; then
    echo -e "${RED}⚠️  Warning: tinytuya.json not found${NC}"
    echo -e "${YELLOW}Device control may not work without Tuya credentials${NC}"
fi

# Start the Flask server
echo -e "${GREEN}Starting Flask server...${NC}"
python3 main.py > ../logs/server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo -e "${YELLOW}Waiting for server to initialize...${NC}"
for i in {1..30}; do
    if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${GREEN}✓ Server started successfully (PID: $SERVER_PID)${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Server failed to start${NC}"
        echo -e "${YELLOW}Check logs/server.log for errors${NC}"
        exit 1
    fi
    sleep 0.5
done

# Open browser
echo -e "${GREEN}Opening dashboard in browser...${NC}"
sleep 1
xdg-open http://192.168.1.15:5000 &

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🦌 Deer Detection System is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Dashboard:       ${YELLOW}http://192.168.1.15:5000${NC}"
echo -e "  Device Manager:  ${YELLOW}http://192.168.1.15:5000/devices${NC}"
echo -e "  Server PID:      ${YELLOW}$SERVER_PID${NC}"
echo -e "  Logs:            ${YELLOW}logs/server.log${NC}"
echo ""
echo -e "To stop the server: ${YELLOW}kill $SERVER_PID${NC}"
echo -e "Or use: ${YELLOW}lsof -ti:5000 | xargs kill${NC}"
echo ""
