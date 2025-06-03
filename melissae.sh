#!/bin/bash

print_banner() {
    echo "
█▀▄▀█ ▄███▄   █    ▄█    ▄▄▄▄▄    ▄▄▄▄▄   ██   ▄███▄  
█ █ █ █▀   ▀  █    ██   █     ▀▄ █     ▀▄ █ █  █▀   ▀ 
█ ▄ █ ██▄▄    █    ██ ▄  ▀▀▀▀▄ ▄  ▀▀▀▀▄   █▄▄█ ██▄▄   
█   █ █▄   ▄▀ ███▄ ▐█  ▀▄▄▄▄▀   ▀▄▄▄▄▀    █  █ █▄   ▄▀
   █  ▀███▀       ▀ ▐                        █ ▀███▀  
  ▀                                         █         
                                           ▀          
    "
}

print_message() {
    echo -e "\e[33m[*] $1\e[0m"
}

print_ok_message() {
    echo -e "\e[32m[*] $1\e[0m"
}

print_port_message() {
    echo -e "\e[32m\e[1mThe new SSH port is: $1\e[0m"
}

show_help() {
    print_banner
    echo "Usage: $0 [option] [modules...]"
    echo ""
    echo "Options:"
    echo "  help                Help menu"
    echo "  install             Install Melissae"
    echo "  start               Start modules"
    echo "  destroy             Destroy the Stack"
    echo "  config-agent        Configure as Multi-Instance Agent"
    echo "  config-server       Configure as Multi-Instance Server"
    echo "  start-agent         Start Multi-Instance Agent"
    echo "  start-server        Start Multi-Instance Server"
    echo "  status-multi        Show Multi-Instance status"
    echo ""
    echo "Modules available :"
    echo "  all        Deploy all modules"
    echo "  web        Web stack + Dashboard"
    echo "  ftp        FTP + Dashboard"
    echo "  ssh        SSH + Dashboard"
    echo "  modbus     Modbus + Dashboard"
    echo ""
    echo "Example :"
    echo "             ./melissae.sh start all"
    echo "             ./melissae.sh config-server"
    echo "             ./melissae.sh config-agent server-ip:8888 api-key"
}
install() {
    print_banner
    print_message "Updating packages"
    sudo apt-get update > /dev/null 2>&1

    print_message "Installing certificates and curl"
    sudo apt-get install ca-certificates curl -y > /dev/null 2>&1

    print_message "Installing Docker's GPG key"
    sudo install -m 0755 -d /etc/apt/keyrings > /dev/null 2>&1
    sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc > /dev/null 2>&1
    sudo chmod a+r /etc/apt/keyrings/docker.asc > /dev/null 2>&1

    print_message "Setting up Docker repository"
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null 2>&1

    print_message "Updating packages again"
    sudo apt-get update > /dev/null 2>&1

    print_message "Installing Docker packages"
    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-compose -y > /dev/null 2>&1

    print_message "Modifying permissions for directories and files"
    chmod -R 777 modules/web/logs
    chmod -R 777 modules/ssh/logs
    chmod -R 777 modules/ftp/logs
    chmod -R 777 modules/modbus/logs

    WORKING_DIRECTORY=$(pwd)

print_message "Adding cleaning scripts to crontabs"

CRONTAB_CONTENT=$(crontab -l 2>/dev/null || echo "")

if ! echo "$CRONTAB_CONTENT" | grep -q "$WORKING_DIRECTORY/scripts/logParser.py"; then
    (echo "$CRONTAB_CONTENT"; echo "* * * * * /usr/bin/python3 $WORKING_DIRECTORY/scripts/logParser.py") | crontab -
    print_message "Added logParser.py to crontab."
else
    print_message "logParser.py is already in crontab. Skipping."
fi

CRONTAB_CONTENT=$(crontab -l 2>/dev/null)

if ! echo "$CRONTAB_CONTENT" | grep -q "$WORKING_DIRECTORY/scripts/threatIntel.py"; then
    (echo "$CRONTAB_CONTENT"; echo "* * * * * /usr/bin/python3 $WORKING_DIRECTORY/scripts/threatIntel.py") | crontab -
    print_message "Added threatIntel.py to crontab."
else
    print_message "threatIntel.py is already in crontab. Skipping."
fi

    print_message "Generating a random port for SSH"
    RANDOM_PORT=$((RANDOM % 10000 + 20000))

    print_message "Modifying SSH configuration with the new port"
    sudo sed -i '/^Port /s/^/#/' /etc/ssh/sshd_config > /dev/null 2>&1
    echo "Port $RANDOM_PORT" | sudo tee -a /etc/ssh/sshd_config > /dev/null 2>&1

    print_port_message $RANDOM_PORT

    read -p "Do you want to restart the SSH server now? (yes/no): " answer

    if [ "$answer" == "yes" ]; then
        print_message "Restarting the SSH server"
        sudo systemctl disable --now ssh.socket > /dev/null 2>&1
        sudo systemctl restart sshd > /dev/null 2>&1
        print_message "The SSH server has been restarted."
        print_ok_message "Installation successful. You can start the stack with './melissae.sh start'."
    else
        print_message "Warning: You need to restart the SSH server to apply the changes. Use 'sudo systemctl restart sshd' to restart later."
    fi
}

start() {
    print_banner
    if [ $# -eq 0 ]; then
        print_message "No module specified."
        show_help
        return
    fi

    modules=("$@")
    services=()

    for module in "${modules[@]}"; do
        case "$module" in
            all)
                services+=("melissae_apache1" "melissae_apache2" "melissae_proxy" "melissae_dashboard" "melissae_ftp" "melissae_ssh" "melissae_modbus")
                ;;
            web)
                services+=("melissae_apache1" "melissae_apache2" "melissae_proxy" "melissae_dashboard")
                ;;
            ftp)
                services+=("melissae_ftp" "melissae_dashboard")
                ;;
            ssh)
                services+=("melissae_ssh" "melissae_dashboard")
                ;;
            modbus)
                services+=("melissae_modbus" "melissae_dashboard")
                ;;
            *)
                echo "Unknown module : $module"
                show_help
                exit 1
                ;;
        esac
    done

    unique_services=($(echo "${services[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

    print_message "Strarting services : ${unique_services[*]}"
    docker-compose up --build --detach "${unique_services[@]}"
    print_ok_message "Services started successfully."
}

destroy() {
    print_banner
    print_message "Destroying containers..."
    docker-compose down > /dev/null 2>&1
    print_ok_message "Containers destroyed"
}

generate_config() {
    local mode=$1
    local server_url=$2
    local api_key=$3
    local config_file="multi-instance.json"
    
    if [ ! -f "$config_file" ]; then
        # Generate a new instance ID and API key
        local instance_id=$(python3 -c "import uuid; print(uuid.uuid4())")
        local new_api_key=$(python3 -c "import hashlib, uuid, time; print(hashlib.sha256(f'{uuid.uuid4()}{time.time()}'.encode()).hexdigest()[:32])")
        
        cat > "$config_file" << EOF
{
  "instance_id": "$instance_id",
  "mode": "$mode",
  "server": {
    "host": "0.0.0.0",
    "port": 8888,
    "api_key": "$new_api_key"
  },
  "agent": {
    "server_url": "$server_url",
    "api_key": "$api_key",
    "sync_interval": 60,
    "timeout": 30
  },
  "timezone": "UTC"
}
EOF
    else
        # Update existing config
        python3 -c "
import json
try:
    with open('$config_file', 'r') as f:
        config = json.load(f)
except:
    config = {}

config['mode'] = '$mode'
if '$server_url':
    config.setdefault('agent', {})['server_url'] = '$server_url'
if '$api_key':
    config.setdefault('agent', {})['api_key'] = '$api_key'

with open('$config_file', 'w') as f:
    json.dump(config, f, indent=2)
"
    fi
}

config_server() {
    print_banner
    print_message "Configuring Melissae as Multi-Instance Server"
    
    generate_config "server" "" ""
    
    # Install Python dependencies
    print_message "Installing Python dependencies..."
    pip3 install requests pytz > /dev/null 2>&1 || {
        sudo apt-get install python3-pip -y > /dev/null 2>&1
        pip3 install requests pytz > /dev/null 2>&1
    }
    
    # Add aggregator to crontab
    WORKING_DIRECTORY=$(pwd)
    CRONTAB_CONTENT=$(crontab -l 2>/dev/null || echo "")
    
    if ! echo "$CRONTAB_CONTENT" | grep -q "$WORKING_DIRECTORY/scripts/multiAggregator.py"; then
        (echo "$CRONTAB_CONTENT"; echo "*/5 * * * * /usr/bin/python3 $WORKING_DIRECTORY/scripts/multiAggregator.py") | crontab -
        print_message "Added multiAggregator.py to crontab (runs every 5 minutes)."
    else
        print_message "multiAggregator.py is already in crontab. Skipping."
    fi
    
    # Get API key from config
    local api_key=$(python3 -c "
import json
try:
    with open('multi-instance.json', 'r') as f:
        config = json.load(f)
    print(config.get('server', {}).get('api_key', 'NOT_FOUND'))
except:
    print('CONFIG_ERROR')
")
    
    print_ok_message "Server configuration complete!"
    echo -e "\e[33m[*] Server will listen on port 8888\e[0m"
    echo -e "\e[33m[*] API Key: $api_key\e[0m"
    echo -e "\e[33m[*] Use './melissae.sh start-server' to start the Multi-Instance server\e[0m"
}

config_agent() {
    print_banner
    
    if [ $# -lt 2 ]; then
        echo "Usage: $0 config-agent <server-url> <api-key>"
        echo "Example: $0 config-agent http://192.168.1.100:8888 abc123def456"
        return 1
    fi
    
    local server_url=$1
    local api_key=$2
    
    print_message "Configuring Melissae as Multi-Instance Agent"
    print_message "Server URL: $server_url"
    print_message "API Key: ${api_key:0:8}..."
    
    generate_config "agent" "$server_url" "$api_key"
    
    # Install Python dependencies
    print_message "Installing Python dependencies..."
    pip3 install requests > /dev/null 2>&1 || {
        sudo apt-get install python3-pip -y > /dev/null 2>&1
        pip3 install requests > /dev/null 2>&1
    }
    
    # Add agent to crontab for periodic sync
    WORKING_DIRECTORY=$(pwd)
    CRONTAB_CONTENT=$(crontab -l 2>/dev/null || echo "")
    
    if ! echo "$CRONTAB_CONTENT" | grep -q "$WORKING_DIRECTORY/scripts/multiInstance.py.*--daemon"; then
        # Remove any existing single-run entries
        CRONTAB_CONTENT=$(echo "$CRONTAB_CONTENT" | grep -v "$WORKING_DIRECTORY/scripts/multiInstance.py")
        (echo "$CRONTAB_CONTENT"; echo "@reboot /usr/bin/python3 $WORKING_DIRECTORY/scripts/multiInstance.py --daemon > /dev/null 2>&1 &") | crontab -
        print_message "Added multiInstance.py agent daemon to crontab."
    else
        print_message "multiInstance.py agent is already in crontab. Skipping."
    fi
    
    print_ok_message "Agent configuration complete!"
    echo -e "\e[33m[*] Agent will sync with server every 60 seconds\e[0m"
    echo -e "\e[33m[*] Use './melissae.sh start-agent' to start the agent manually\e[0m"
}

start_server() {
    print_banner
    print_message "Starting Multi-Instance Server..."
    
    if [ ! -f "multi-instance.json" ]; then
        echo -e "\e[31m[ERROR] No multi-instance configuration found. Run './melissae.sh config-server' first.\e[0m"
        return 1
    fi
    
    # Check if server is already running
    if pgrep -f "multiServer.py" > /dev/null; then
        print_message "Multi-Instance Server is already running"
        return 0
    fi
    
    # Start server in background
    python3 scripts/multiServer.py --config multi-instance.json > multi-instance-server.log 2>&1 &
    local server_pid=$!
    
    # Wait a moment and check if it started
    sleep 2
    if kill -0 "$server_pid" 2>/dev/null; then
        echo "$server_pid" > multi-instance-server.pid
        print_ok_message "Multi-Instance Server started (PID: $server_pid)"
        print_message "Server log: tail -f multi-instance-server.log"
    else
        echo -e "\e[31m[ERROR] Failed to start Multi-Instance Server. Check multi-instance-server.log\e[0m"
        return 1
    fi
}

start_agent() {
    print_banner
    print_message "Starting Multi-Instance Agent..."
    
    if [ ! -f "multi-instance.json" ]; then
        echo -e "\e[31m[ERROR] No multi-instance configuration found. Run './melissae.sh config-agent' first.\e[0m"
        return 1
    fi
    
    # Check if agent is already running
    if pgrep -f "multiInstance.py.*--daemon" > /dev/null; then
        print_message "Multi-Instance Agent is already running"
        return 0
    fi
    
    # Start agent in background
    python3 scripts/multiInstance.py --config multi-instance.json --daemon > multi-instance-agent.log 2>&1 &
    local agent_pid=$!
    
    # Wait a moment and check if it started
    sleep 2
    if kill -0 "$agent_pid" 2>/dev/null; then
        echo "$agent_pid" > multi-instance-agent.pid
        print_ok_message "Multi-Instance Agent started (PID: $agent_pid)"
        print_message "Agent log: tail -f multi-instance-agent.log"
    else
        echo -e "\e[31m[ERROR] Failed to start Multi-Instance Agent. Check multi-instance-agent.log\e[0m"
        return 1
    fi
}

status_multi() {
    print_banner
    print_message "Multi-Instance Status"
    
    if [ ! -f "multi-instance.json" ]; then
        echo -e "\e[31m[*] No multi-instance configuration found\e[0m"
        return 1
    fi
    
    # Show configuration
    local mode=$(python3 -c "
import json
try:
    with open('multi-instance.json', 'r') as f:
        config = json.load(f)
    print(config.get('mode', 'unknown'))
except:
    print('error')
")
    
    echo -e "\e[33m[*] Mode: $mode\e[0m"
    
    if [ "$mode" = "server" ]; then
        # Check server status
        if pgrep -f "multiServer.py" > /dev/null; then
            local server_pid=$(pgrep -f "multiServer.py")
            echo -e "\e[32m[*] Server: Running (PID: $server_pid)\e[0m"
            
            # Try to get server status via API
            local api_key=$(python3 -c "
import json
try:
    with open('multi-instance.json', 'r') as f:
        config = json.load(f)
    print(config.get('server', {}).get('api_key', ''))
except:
    print('')
")
            
            if [ -n "$api_key" ]; then
                local port=$(python3 -c "
import json
try:
    with open('multi-instance.json', 'r') as f:
        config = json.load(f)
    print(config.get('server', {}).get('port', 8888))
except:
    print('8888')
")
                
                # Test server API
                local status_response=$(curl -s -H "Authorization: Bearer $api_key" "http://localhost:$port/api/status" 2>/dev/null || echo "")
                if [ -n "$status_response" ]; then
                    echo -e "\e[32m[*] Server API: Responding\e[0m"
                    local connected_instances=$(echo "$status_response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('connected_instances', 0))
except:
    print('0')
")
                    echo -e "\e[33m[*] Connected Instances: $connected_instances\e[0m"
                else
                    echo -e "\e[31m[*] Server API: Not responding\e[0m"
                fi
            fi
        else
            echo -e "\e[31m[*] Server: Not running\e[0m"
        fi
    elif [ "$mode" = "agent" ]; then
        # Check agent status
        if pgrep -f "multiInstance.py.*--daemon" > /dev/null; then
            local agent_pid=$(pgrep -f "multiInstance.py.*--daemon")
            echo -e "\e[32m[*] Agent: Running (PID: $agent_pid)\e[0m"
        else
            echo -e "\e[31m[*] Agent: Not running\e[0m"
        fi
        
        # Show server connection info
        local server_url=$(python3 -c "
import json
try:
    with open('multi-instance.json', 'r') as f:
        config = json.load(f)
    print(config.get('agent', {}).get('server_url', 'not configured'))
except:
    print('error')
")
        echo -e "\e[33m[*] Server URL: $server_url\e[0m"
    fi
    
    # Show log files
    if [ -f "multi-instance-server.log" ]; then
        echo -e "\e[33m[*] Server log: multi-instance-server.log\e[0m"
    fi
    if [ -f "multi-instance-agent.log" ]; then
        echo -e "\e[33m[*] Agent log: multi-instance-agent.log\e[0m"
    fi
}

if [ $# -eq 0 ]; then
    show_help
else
    case "$1" in
        help)
            show_help
            ;;
        install)
            install
            ;;
        start)
            shift
            start "$@"
            ;;
        destroy)
            destroy
            ;;
        config-server)
            config_server
            ;;
        config-agent)
            shift
            config_agent "$@"
            ;;
        start-server)
            start_server
            ;;
        start-agent)
            start_agent
            ;;
        status-multi)
            status_multi
            ;;
        *)
            echo "Option invalide : $1"
            show_help
            exit 1
            ;;
    esac
fi
