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
        sleep 2  # Give browser time to open
        exit 0
    fi
fi

# Navigate to server directory
cd "$(dirname "$0")/server"

# Function to show progress
show_progress() {
    local percent=$1
    local message=$2
    local bar_length=40
    local filled=$((percent * bar_length / 100))
    local empty=$((bar_length - filled))

    printf "\r${YELLOW}[%${filled}s%${empty}s] %3d%% - %s${NC}" \
        "$(printf '█%.0s' $(seq 1 $filled))" \
        "$(printf ' %.0s' $(seq 1 $empty))" \
        "$percent" \
        "$message"
}

# Function to detect GPU and select appropriate requirements file
detect_hardware() {
    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            echo -e "${GREEN}🎮 NVIDIA GPU detected - using GPU-accelerated PyTorch${NC}" >&2
            echo "requirements-gpu.txt"
            return
        fi
    fi

    # No GPU detected - use CPU-only version
    echo -e "${YELLOW}💻 No GPU detected - using CPU-optimized PyTorch (~1.7GB)${NC}" >&2
    echo "requirements-cpu.txt"
}

# Check if we can use system packages (preferred - faster startup)
USE_SYSTEM_PACKAGES=false
if python3 -c "import flask; import cv2; import ultralytics; import torch" 2>/dev/null; then
    echo -e "${GREEN}✓ Using system-wide Python packages${NC}"
    USE_SYSTEM_PACKAGES=true
fi

# Check if venv needs to be rebuilt (for portability after moving project)
VENV_NEEDS_REBUILD=false
if [ "$USE_SYSTEM_PACKAGES" = false ] && [ -d "venv" ] && [ -f "venv/pyvenv.cfg" ]; then
    # Get the expected venv path from current location
    CURRENT_VENV_PATH="$(pwd)/venv"
    # Get the actual venv path from config
    CONFIGURED_VENV_PATH=$(grep "^command = " venv/pyvenv.cfg | sed 's/.*venv //' | tr -d '\r')

    if [ "$CONFIGURED_VENV_PATH" != "$CURRENT_VENV_PATH" ]; then
        VENV_NEEDS_REBUILD=true
        echo -e "${YELLOW}📦 Project location changed - rebuilding virtual environment...${NC}"
        echo -e "${YELLOW}   Old location: $CONFIGURED_VENV_PATH${NC}"
        echo -e "${YELLOW}   New location: $CURRENT_VENV_PATH${NC}"
        echo ""

        show_progress 0 "Preparing to rebuild..."
        sleep 0.5

        show_progress 20 "Removing old virtual environment..."
        rm -rf venv

        show_progress 40 "Creating new virtual environment..."
        python3 -m venv venv > /dev/null 2>&1

        show_progress 60 "Activating environment..."
        source venv/bin/activate

        show_progress 70 "Upgrading pip..."
        pip install --upgrade pip -q > /dev/null 2>&1

        show_progress 75 "Detecting hardware..."
        REQUIREMENTS_FILE=$(detect_hardware)

        if [ "$REQUIREMENTS_FILE" = "requirements-cpu.txt" ]; then
            show_progress 78 "Installing CPU-only PyTorch..."
            pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu > /dev/null 2>&1
            show_progress 82 "Installing dependencies..."
            pip install -q -r "$REQUIREMENTS_FILE" > /dev/null 2>&1
        else
            show_progress 80 "Installing dependencies ($REQUIREMENTS_FILE)..."
            pip install -q -r "$REQUIREMENTS_FILE" > /dev/null 2>&1
        fi

        show_progress 100 "Complete!"
        echo ""
        echo -e "${GREEN}✓ Virtual environment rebuilt successfully${NC}"
        echo ""
    fi
fi

# Check if virtual environment exists, create if not (only if system packages not available)
if [ "$USE_SYSTEM_PACKAGES" = false ] && [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment (skip if using system packages or already activated during rebuild)
if [ "$USE_SYSTEM_PACKAGES" = false ] && [ "$VENV_NEEDS_REBUILD" = false ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate

    # Detect hardware and select appropriate requirements file
    REQUIREMENTS_FILE=$(detect_hardware)

    # Install/update requirements
    echo -e "${YELLOW}Checking dependencies...${NC}"
    if [ "$REQUIREMENTS_FILE" = "requirements-cpu.txt" ]; then
        # CPU version requires special PyTorch installation
        pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
        pip install -q -r "$REQUIREMENTS_FILE"
    else
        pip install -q -r "$REQUIREMENTS_FILE"
    fi
fi

# Check for required files
if [ ! -f "yolov8n.pt" ]; then
    echo -e "${RED}⚠️  Warning: yolov8n.pt model file not found${NC}"
    echo -e "${YELLOW}The detection system will download it on first run${NC}"
fi

if [ ! -f "tinytuya.json" ]; then
    echo -e "${RED}⚠️  Warning: tinytuya.json not found${NC}"
    echo -e "${YELLOW}Device control may not work without Tuya credentials${NC}"
fi

# Start the Flask server with nohup (keeps running after terminal closes)
echo -e "${GREEN}Starting Flask server...${NC}"
if [ "$USE_SYSTEM_PACKAGES" = true ]; then
    nohup python3 main.py > ../logs/server.log 2>&1 &
else
    nohup python3 main.py > ../logs/server.log 2>&1 &
fi
SERVER_PID=$!
echo $SERVER_PID > ../server.pid

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
echo -e "Server will keep running even if you close this terminal."
echo -e "To stop the server: ${YELLOW}./stop.sh${NC}"
echo ""
echo -e "${YELLOW}Press any key to close this window...${NC}"
read -n 1 -s
