# Glacier: Advanced Website Management Tool

Glacier is a powerful, user-friendly command-line tool designed to simplify website management using Docker containers. It automates the process of setting up, deploying, and managing multiple websites across single or multiple servers, handling Nginx configurations, SSL certificates, PHP environments, databases, and more.

## Features

- Easy setup and management of multiple websites
- Automatic Nginx configuration generation
- SSL certificate management (including wildcard SSL)
- Support for multiple PHP versions (7.4, 8.0, 8.1, 8.2, 8.3)
- Git integration for easy deployment
- Docker-based isolation for security and resource management
- Database creation and management
- Website backup and restore functionality
- Staging environment creation and promotion
- FTP access setup
- Website statistics with GoAccess
- Redis setup
- CDN setup assistance
- Monitoring with Prometheus and Grafana
- Multi-server support
- Docker image management
- Plugin system for extensibility
- Cross-platform support (Linux and Windows)

## Prerequisites

- Python 3.6 or higher
- Docker and Docker Compose (will be installed automatically if not present)

## Installation

1. Clone the Glacier repository:
   ```
   git clone https://github.com/yourusername/glacier.git
   cd glacier
   ```

2. Run the Glacier script:
   ```
   python glacier.py
   ```

The script will automatically install all required dependencies.

## Usage

Running `glacier.py` will launch an interactive menu with the following options:

1. Create website
2. Rebuild website
3. Create database
4. Delete database
5. Backup website
6. Restore website
7. Add custom Nginx config
8. Setup website statistics
9. Setup FTP access
10. Create staging environment
11. Promote staging to production
12. Setup wildcard SSL
13. Setup Redis
14. Setup CDN
15. Setup monitoring
16. Setup alerts
17. Add server
18. Remove server
19. List servers
20. Pull Docker image
21. List Docker images
22. Remove Docker image
23. Run plugin
24. Exit

## Key Features Explained

### Multi-PHP Support
Glacier supports PHP versions 7.4, 8.0, 8.1, 8.2, and 8.3, allowing you to choose the appropriate version for each website.

### Database Management
Easily create and delete MySQL databases for your websites.

### Backup and Restore
Create backups of your websites and restore them when needed.

### Staging Environments
Create staging environments for testing changes before pushing to production.

### SSL Certificates
Manage SSL certificates, including support for wildcard SSL.

### Website Statistics
Set up GoAccess for real-time web analytics.

### FTP Access
Quickly set up FTP access for your websites.

### CDN Integration
Get guidance on setting up Content Delivery Networks for your websites.

### Monitoring and Alerts
Set up Prometheus and Grafana for monitoring, with customizable alerts.

### Multi-Server Support
Manage websites across multiple servers from a single Glacier instance.

### Docker Management
Pull, list, and remove Docker images directly from the Glacier interface.

### Plugin System
Extend Glacier's functionality with custom plugins.

## Directory Structure

glacier/
├── nginx/
├── sites/
├── certs/
├── backups/
├── docker-compose.yml
├── Dockerfile-php
└── plugins/

## Troubleshooting

If you encounter any issues:
1. Check the logs for the specific service or website
2. Ensure your domain's DNS is correctly configured
3. Verify that required ports are open on your server(s)
4. For Windows-specific issues, consider using Windows Subsystem for Linux (WSL)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.