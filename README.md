# Melissae

![logo](https://github.com/user-attachments/assets/99609143-d9df-43f9-a824-befd98895cb9)

---

Melissae is a modular, containerized honeypot framework built to emulate real-world network services. It is designed for cybersecurity researchers, analysts, and SOC teams to detect, analyze, and better understand malicious activity on their infrastructure.

Each service module runs in its own container, allowing flexible deployment and isolated execution, while collected logs are centralized, parsed, and enriched via a dedicated processing pipeline.

The project includes a fully functional dashboard offering real-time visibility into attacker behavior, threat scoring, and IOC export, making Melissae not just a honeypot, but a lightweight threat intelligence platform.

## Table of Contents

1. [Overview](#overview) 
    - [Key Features](#key-features) 
2. [Infrastructure](#infrastructure)
    - [Schema](#schema)
    - [Workflow](#workflow) 
    - [File Tree](#file-tree)
3. [Modules](#modules)
    - [Web](#web) 
    - [SSH](#ssh) 
    - [FTP](#ftp)
    - [Modbus](#modbus) 
4. [Search Engine](#search-engine)
5. [Threat Intelligence](#threat-intelligence)
6. [Getting Started](#getting-started)
    - [Installation](#installation)
    - [Starting up the Stack](#starting-up-the-stack)
    - [Accessing the Dashboard](#accessing-the-dashboard)
    - [Destroying the Stack](#destroying-the-stack)
7. [Contributing](#contributing)
8. [Credits](#credits)

---
## Overview

#### Key Features

**Modular Service Support**: Configure Melissae to expose between 1 and 4 services simultaneously, allowing for flexible deployment scenarios tailored to your specific security needs. See [contributing](#contributing) if you're interested in developing new modules.  
  
  
**Centralized Management Dashboard**: Monitor and manage your honeypot through a web-based dashboard, which offers:
- **Statistical Analysis**: Visualize attack patterns, trends, and frequency.
- **Advanced Log Search**: Utilize the Melissae Query Language (MQL), a simple query language (that will be developed more in the future), to perform searches within the captured logs.
- **Data Export**: Export logs or Indicators of Compromise (IOCs) in JSON format, filtered according to specific criteria such as time, service type, or threat verdict.
- **Threat Scoring**: Assess attacker danger levels with a built-in scoring system, categorizing threats by severity. This helps prioritize responses and allocate resources effectively.

---

## Infrastructure

> [!WARNING]  
> Please use this tool with care, and remember to use it on a dedicated secure server that is properly isolated from your infrastructure.

The infrastructure is fully containerized with docker, and modules can be deployed on demand. The dashboard is always deployed locally and accessible via port forwarding.

#### Schema

![Diagram](https://github.com/user-attachments/assets/6db12dcd-816c-4616-aed0-e44a94f2c0e3)

---

#### File Tree

```bash
-- Melissae
    |-- README.md
    |-- dashboard
    |   |-- conf
    |   |   |-- dashboard.conf
    |   |-- css
    |   |   |-- styles.css
    |   |   |-- threat-intel.css
    |   |-- dashboard.html
    |   |-- img
    |   |   |-- favicon.ico
    |   |   |-- logo.png
    |   |-- js
    |   |   |-- backgroundDisplay.js
    |   |   |-- dashboardDisplay.js
    |   |   |-- main.js
    |   |   |-- searchDisplay.js
    |   |   |-- searchEngine.js
    |   |   |-- threatintelDisplay.js
    |   |-- json
    |   |   |-- logs.json
    |   |    -- threats.json
    |   |-- search.html
    |   |-- threat-intel.html
    |-- docker-compose.yml
    |-- melissae.sh
    |-- modules
    |   |-- ftp
    |   |   |-- logs
    |   |       |-- vsftpd.log
    |   |   |-- server
    |   |       |-- ftpuser
    |   |           |-- test.txt
    |   |-- ssh
    |   |   |-- Dockerfile
    |   |   |-- logs
    |   |       |-- commands.log
    |   |       |-- sshd.log
    |   |-- modbus
    |   |   |-- Dockerfile
    |   |   |-- server
    |   |       |-- server.py
    |   |   |-- logs
    |   |       |-- modbus.log
    |    -- web
    |       |-- Dockerfile
    |       |-- conf
    |       |   |-- web.conf
    |       |   |-- proxy.conf
    |       |-- logs
    |       |   |-- access.log
    |       |   |-- error.log
    |       |-- server
    |           |-- index.html
    |-- scripts
        |-- logParser.py
        |-- threatIntel.py
```

---

#### Workflow

The various module logs are processed by logParser.py, which parses and formats them. In turn, threatIntel.py processes these formatted logs to enrich Threat Intelligence.

![Diagram-Workflow](https://github.com/user-attachments/assets/021fa12f-8561-4492-8164-2af032a211fb)


---

## Modules
The choice of modular, containerized deployment means that contributors can easily develop new modules. 
There are currently 4 native modules:

#### Web

| Type | Image | Container name|
| :-------------------: | :----------: | :----------: |
| Proxy     | nginx:latest     | melissae_proxy       |
| Web Server             | httpd:2.4-alpine with apache2    | melissae_apache1  |
| Web Server               | httpd:2.4-alpine with apache2     | melissae_apache2       |

- Logs format

```json
[
  {
    "protocol": "http",
    "date": "2025-04-16",
    "hour": "11:47:08",
    "ip": "192.168.X.X",
    "action": "GET",
    "path": "/",
    "user-agent": "Mozilla/5.0"
  }
]
```


- Usage
  - By default, Melissae provides you a basic configuration for both proxy and web servers containers, those configurations are located in `modules/web/conf`
  - Add the files you need for the website to be exposed via honeypot in `modules/web/server`



---

#### SSH

| Type | Image | Container name|
| :-------------------: | :----------: | :----------: |
| SSH Server            | ubuntu:latest with openssh     | melissae_ssh       |


- Logs format

```json
[
  {
    "protocol": "ssh",
    "date": "2025-04-16",
    "hour": "11:48:09",
    "ip": "192.168.X.X",
    "action": "Login failed with invalid user",
    "user": "test"
  }
]
```

- Usage
  - You need to modify your module credentials here : `modules/ssh/Dockerfile` (Default : `user:admin`)

---

#### FTP

| Type | Image | Container name|
| :-------------------: | :----------: | :----------: |
| FTP Server            | fauria/vsftpd     | melissae_ftp      |

- Logs format

```json
[
  {
    "protocol": "ftp",
    "date": "2025-04-16",
    "hour": "11:48:37",
    "ip": "192.168.27.65",
    "action": "Login failed",
    "user": "test"
  }
]
```

- Usage
  - The shared repository with the ftp container is `modules/ftp/server`
  - You need to modify your module credentials here : `docker-compose.yml` (Default `ftpuser:ftppass`)

---

#### Modbus

| Type | Image | Container name|
| :-------------------: | :----------: | :----------: |
| Modbus TCP Server     | python:3.11-slim with custom modbus server | melissae_modbus |

- Logs format

```json
[
  {
    "protocol": "modbus",
    "date": "2025-05-30",
    "hour": "10:38:23",
    "ip": "172.18.0.1",
    "action": "Read request - Read Holding Registers"
  },
  {
    "protocol": "modbus",
    "date": "2025-05-30", 
    "hour": "10:41:22",
    "ip": "172.18.0.1",
    "action": "Write attempt - Write Multiple Registers"
  }
]
```

- Features
  - **Industrial PLC Emulation**: Simulates Siemens S7-1200 and Schneider Electric M340 PLCs
  - **Randomized Device Identifiers**: Generates unique serial numbers and firmware versions on each startup
  - **Protocol Detection**: Logs all Modbus function codes (read/write operations)
  - **Threat Escalation**: Write attempts trigger high-severity threat alerts

- Usage
  - **Default Profile**: Siemens S7-1200 (modify in `modules/modbus/Dockerfile` to use `schneider` profile)
  - **Port**: Standard Modbus TCP port 502
  - **Device Profiles**:
    - **Siemens**: S7-xxxxxx serials, V3.x-V4.x firmware, 1000 registers
    - **Schneider**: M340-xxxxx-X serials, V2.x-V3.x firmware, 2000 registers

---

## Threat Intelligence

The Threat Intelligence section of the dashboard provides a simple visual overview of detected threats.  
(Really) basic scoring rules have been implemented, but they are intended to be improved in the future.
See [contributing](#contributing) if you're interested in developing the threat intelligence.

There are 5 different verdicts:

- **Benign**: Threat requested the web module < 50 times  
- **Suspicious**: Threat requested the web module > 50 times OR (attempted to connect using SSH OR FTP) OR performed Modbus read operations
- **Malicious**: Threat successfully connected via SSH OR FTP OR (performed Modbus writes + other failed attempts)
- **Nefarious**: Threat connected via both SSH AND FTP OR (performed Modbus write operations + a successful connection via SSH or FTP)

![threat-intel](https://github.com/user-attachments/assets/b6e9fc77-18b5-4528-a08a-a8e5cbeec82c)


IoCs can be exported in json.

**IoC Format**

```json
[
  {
    "type": "ip",
    "ip": "192.168.X.X",
    "protocol-score": 3,
    "verdict": "suspicious"
  }
]
```


---

## Search Engine

#### Main Features

- **Search with logical operators**: Use operators to combine multiple criteria in your search.
- **Field-specific filters**: Search within specific fields like user, ip, protocol, date, hour, action, user-agent, or path using the syntax field:value
- **Global search**: If no field is specified, the search applies to all log fields.
- **Export results**: A button allows exporting the filtered logs.

#### Operators

`AND / and`
`OR / or`
`NOT / not / !`

#### Examples

```
user:root and protocol:ssh
ip:192.168.X.X or ip:192.168.X.Y or ip:192.168.X.Z
protocol:http and not action:success
protocol:modbus and action:write
user:admin or not path:/login
!ip:192.168.X.X and action:failed
protocol:modbus and action:read
```

![search](https://github.com/user-attachments/assets/e8476368-baba-4c22-a1de-b99ffc2150c5)

#### Limitations

Currently, the search engine supports only a few operations at a time. See [contributing](#contributing) if you're interested in developing the search engine.

---

## Getting Started

#### Installation

Clone the repository :
`git clone https://github.com/ilostmypassword/Melissae.git`

Give execution rights to the script :

```bash
cd Melissae/
chmod +x melissae.sh
```

Install Melissae :

> [!CAUTION]
> Your SSH port will be modified and given to you at the end of the installation script. Note it carefully.

```bash
./melissae.sh install
```

Add your user in the docker group :

```bash
sudo su
usermod -aG docker your_username
```

> [!NOTE]  
> After adding the user to the docker group, you will likely need to reconnect via SSH using the generated port that was provided to you. You can connect directly with the command provided in "[accessing the Dashboard](#accessing-the-dashboard)"

---

#### Starting up the stack

> [!IMPORTANT]  
> Before launching your stack, don't forget to check the modules usage here : [Modules](#modules)

**Start your stack**

```bash
./melissae.sh start [module 1] [module 2] [...]
```

Available modules: `all`, `web`, `ssh`, `ftp`, `modbus`

Examples:
```bash
# Start all modules
./melissae.sh start all

# Start specific modules
./melissae.sh start web ssh modbus

# Start only Modbus honeypot
./melissae.sh start modbus
```
    
Your stack should now be deployed.
If you are already connected with the port forwarding activated, your dashboard is accessible on : 

`http://localhost:8080`

But if you didn't, and you want to access the dashboard, go to "[Accessing the Dashboard](#accessing-the-dashboard)"

---

#### Accessing the dashboard

Connect to your server with this command and the newly generated port. 
This command will allow you to forward the dashboard to your localhost. 

```bash
ssh -L 8080:localhost:9999 user@server -p new_port
```

Then access the dasboard in your browser :

`http://localhost:8080/`

![dashboard](https://github.com/user-attachments/assets/0d8c4d30-eb62-49a0-af35-86af3e1e3940)


---

#### Destroying the stack

You can destroy your stack easily with :

```bash
./melissae.sh destroy
```

---

## Contributing

This project is of course open to contributions, and there are a number of areas of work to be developed. For those who wish to contribute, you can join the discord server :

Discord : https://discord.gg/RXWn85cnYm

Priority Tasks :

 - [x] **Modbus Industrial Honeypot Module** - Complete TCP honeypot with PLC emulation
 - [ ] New modules need to be developed (SNMP, MQTT, etc.)
 - [ ] Improve the search engine
 - [ ] Threat Intelligence must be developed

## Credits

Thank you to all contributors for helping the project move forward.

- summoningshells (https://github.com/summoningshells)
