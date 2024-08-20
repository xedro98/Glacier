# Glacier: Easy Website Management

Glacier is a powerful, user-friendly command-line tool designed to simplify website management using Docker containers. It automates the process of setting up, deploying, and managing multiple websites on a single server, handling Nginx configurations, SSL certificates, and PHP environments with ease.

## Features

- Easy setup and management of multiple websites
- Automatic Nginx configuration generation
- SSL certificate management with Let's Encrypt
- Support for PHP-based websites
- Git integration for easy deployment
- Docker-based isolation for security and resource management
- Interactive CLI for user-friendly operation

## Prerequisites

- Ubuntu-based system (tested on Ubuntu 20.04 LTS)
- Python 3.6 or higher
- Docker and Docker Compose (will be installed automatically if not present)

## Installation

1. Clone the Glacier repository:
   ```
   git clone https://github.com/yourusername/glacier.git
   cd glacier
   ```

2. Make the script executable:
   ```
   chmod +x glacier.py
   ```

## Usage

Run the Glacier script:

```
./glacier.py
```

This will launch an interactive menu with the following options:

1. **Setup Glacier**: Initialize Glacier and install prerequisites
2. **Create a new website**: Set up a new website
3. **Rebuild an existing website**: Update an existing website
4. **Start Glacier services**: Start all Docker containers
5. **Stop Glacier services**: Stop all Docker containers
6. **View website logs**: Display logs for a specific website
7. **Delete a website**: Remove a website and its configuration
8. **Install PHP extension**: Add a new PHP extension to the environment
9. **Uninstall Glacier**: Remove Glacier and all associated data
10. **Exit**: Quit the Glacier application

## Commands

### Setup

Initializes Glacier, installs prerequisites, and sets up the Docker environment.

### Create a new website

Creates a new website. You'll be prompted for:
- Domain name
- Git repository URL (optional)
- Whether to skip SSL setup

### Rebuild an existing website

Updates an existing website. You'll be prompted for:
- Domain name
- Git repository URL to update from (optional)
- Whether to reconfigure SSL
- Whether to force rebuild without confirmation

### Start Glacier services

Starts all Docker containers associated with Glacier.

### Stop Glacier services

Stops all Docker containers associated with Glacier.

### View website logs

Displays logs for a specific website. You'll be prompted for the domain name.

### Delete a website

Removes a website and its configuration. You'll be prompted for:
- Domain name
- Whether to force deletion without confirmation

### Install PHP extension

Installs a new PHP extension. You'll be prompted for the extension name.

### Uninstall Glacier

Removes Glacier and all associated data. You'll be asked to confirm this action.

## How It Works

Glacier uses Docker to create isolated environments for each website. It automatically generates Nginx configurations, manages SSL certificates using Let's Encrypt, and provides an easy-to-use interface for common website management tasks.

The application creates the following directory structure:

```
glacier/
├── nginx/
├── sites/
├── certs/
├── docker-compose.yml
└── Dockerfile-php
```

- `nginx/`: Contains Nginx configuration files for each website
- `sites/`: Stores the actual website files
- `certs/`: Stores SSL certificates
- `docker-compose.yml`: Defines the Docker services
- `Dockerfile-php`: Defines the PHP environment

## SSL Certificates

Glacier uses Let's Encrypt for SSL certificates. When setting up SSL for a domain, you'll be prompted to create a TXT record for DNS verification. The script will guide you through this process.

## Troubleshooting

If you encounter any issues:
1. Check the logs using the "View website logs" option
2. Ensure your domain's DNS is correctly configured
3. Verify that ports 80 and 443 are open on your server

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.