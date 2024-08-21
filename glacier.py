#!/usr/bin/env python3

import sys
import subprocess
import os
import logging
import yaml
import shutil
import time
import socket
from pathlib import Path
import requests
import tempfile
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime
import random
import string
import dns.resolver
import select
import signal
import re
import tarfile
import threading
import schedule
import mysql.connector
from mysql.connector import Error
import docker

# Initialize Rich console for formatted output
from rich.console import Console
console = Console()

def install_dependencies():
    dependencies = [
        'inquirer',
        'rich',
        'pyyaml',
        'gitpython',
        'flask',
        'dnspython',
        'requests',
        'cryptography',
        'schedule',
        'mysql-connector-python',
        'docker'
    ]
    
    console.print("Checking and installing required dependencies...", style="bold blue")
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            console.print(f"Installing {dep}...", style="yellow")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

install_dependencies()

import inquirer
from rich.panel import Panel
from rich.text import Text

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set the base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_command(command):
    """Execute a shell command and return its output"""
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()

def install_prerequisites():
    """Install necessary system packages and Python libraries"""
    logger.info("Installing prerequisites...")
    commands = [
        f"{sys.executable} -m pip install --upgrade pip",
        f"{sys.executable} -m pip install docker-compose"
    ]
    for cmd in commands:
        logger.info(f"Running: {cmd}")
        returncode, stdout, stderr = run_command(cmd)
        if returncode != 0:
            logger.error(f"Error executing {cmd}: {stderr}")
            if inquirer.confirm("Do you want to continue with the next command?", default=False):
                continue
            else:
                return False
        logger.info(stdout)
    logger.info("Prerequisites installed successfully.")
    return True

def setup_php_containers():
    php_versions = ['7.4', '8.0', '8.1', '8.2', '8.3']
    for version in php_versions:
        dockerfile_content = f"""
FROM php:{version}-fpm

RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) gd

RUN docker-php-ext-install pdo pdo_mysql
"""
        with open(os.path.join(BASE_DIR, f'Dockerfile-php{version}'), 'w') as f:
            f.write(dockerfile_content)

        docker_compose['services'][f'php{version}'] = {
            'build': {
                'context': '.',
                'dockerfile': f'Dockerfile-php{version}'
            },
            'volumes': [
                './sites:/var/www/html'
            ],
            'restart': 'always',
        }

def setup_ssl_renewal():
    # Placeholder for SSL renewal setup
    pass

def setup_fail2ban():
    # Placeholder for Fail2Ban setup (not applicable on Windows)
    console.print("Fail2Ban setup is not available on Windows.", style="yellow")

def setup_ufw_firewall():
    # Placeholder for UFW firewall setup (not applicable on Windows)
    console.print("UFW firewall setup is not available on Windows. Consider using Windows Firewall.", style="yellow")

def setup_monitoring():
    docker_compose['services']['prometheus'] = {
        'image': 'prom/prometheus',
        'volumes': [
            './prometheus:/etc/prometheus',
            './prometheus_data:/prometheus'
        ],
        'command': [
            '--config.file=/etc/prometheus/prometheus.yml',
            '--storage.tsdb.path=/prometheus',
            '--web.console.libraries=/usr/share/prometheus/console_libraries',
            '--web.console.templates=/usr/share/prometheus/consoles'
        ],
        'ports': ['9090:9090'],
        'restart': 'always',
    }
    
    docker_compose['services']['grafana'] = {
        'image': 'grafana/grafana',
        'volumes': ['./grafana_data:/var/lib/grafana'],
        'ports': ['3000:3000'],
        'restart': 'always',
    }
    
    prometheus_config = """
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
"""
    prometheus_config_path = os.path.join(BASE_DIR, 'prometheus', 'prometheus.yml')
    os.makedirs(os.path.dirname(prometheus_config_path), exist_ok=True)
    
    with open(prometheus_config_path, 'w') as f:
        f.write(prometheus_config)
    
    console.print("Monitoring setup with Prometheus and Grafana", style="bold green")

def setup(force=False):
    """Set up Glacier and install prerequisites"""
    if force or inquirer.confirm(message="Force reinstallation of prerequisites?", default=False):
        with console.status("[bold green]Installing prerequisites...") as status:
            install_prerequisites()
        console.print("Prerequisites installed successfully.", style="bold green")
    
    os.makedirs(os.path.join(BASE_DIR, 'nginx'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'sites'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'certs'), exist_ok=True)

    global docker_compose
    docker_compose = {
        'version': '3',
        'services': {
            'nginx': {
                'image': 'nginx:latest',
                'ports': ['80:80', '443:443'],
                'volumes': [
                    './nginx:/etc/nginx/conf.d',
                    './sites:/var/www/html',
                    './certs:/etc/letsencrypt',
                    './logs/nginx:/var/log/nginx'
                ],
                'depends_on': ['php7.4', 'php8.0', 'php8.1', 'php8.2', 'php8.3'],
                'restart': 'always',
            }
        }
    }

    setup_php_containers()
    setup_ssl_renewal()
    setup_fail2ban()
    setup_ufw_firewall()
    setup_monitoring()

    with open(os.path.join(BASE_DIR, 'docker-compose.yml'), 'w') as f:
        yaml.dump(docker_compose, f)

    console.print("Glacier setup completed successfully.", style="bold green")

def create_nginx_conf(domain, ssl=True, wildcard=False):
    conf_content = f"""
server {{
    listen 80;
    server_name {domain} www.{domain};
    root /var/www/html/{domain};
    index index.php index.html index.htm;

    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}

    location ~ \.php$ {{
        fastcgi_pass php8.0:9000;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }}
}}
"""
    if ssl:
        conf_content += f"""
server {{
    listen 443 ssl http2;
    server_name {domain} www.{domain};
    root /var/www/html/{domain};
    index index.php index.html index.htm;

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;

    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}

    location ~ \.php$ {{
        fastcgi_pass php8.0:9000;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }}
}}
"""
    
    conf_path = os.path.join(BASE_DIR, 'nginx', f'{domain}.conf')
    with open(conf_path, 'w') as f:
        f.write(conf_content)

def create(domain, git=None, skip_ssl=False):
    site_dir = os.path.join(BASE_DIR, 'sites', domain)
    os.makedirs(site_dir, exist_ok=True)

    if git:
        run_command(f"git clone {git} {site_dir}")
    else:
        index_html = f"<h1>Welcome to {domain}</h1>"
        with open(os.path.join(site_dir, 'index.html'), 'w') as f:
            f.write(index_html)

    create_nginx_conf(domain, ssl=not skip_ssl)
    
    if not skip_ssl:
        setup_ssl(domain)
    
    run_command(f"docker-compose up -d")
    console.print(f"Website {domain} created successfully", style="bold green")

def rebuild(domain, git=None, reconfigure_ssl=False):
    site_dir = os.path.join(BASE_DIR, 'sites', domain)
    
    if git:
        run_command(f"git -C {site_dir} pull")
    
    if reconfigure_ssl:
        setup_ssl(domain)
    
    create_nginx_conf(domain, ssl=True)
    run_command(f"docker-compose up -d --build")
    console.print(f"Website {domain} rebuilt successfully", style="bold green")

def setup_ssl(domain):
    # Placeholder for SSL setup (consider using certbot for Windows or a manual process)
    console.print(f"SSL setup for {domain} is not implemented in this version.", style="yellow")

def create_database(domain, db_name, db_user, db_password):
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=get_mysql_root_password()
        )
        cursor = conn.cursor()
        
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'")
        cursor.execute(f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        
        conn.close()
        console.print(f"Database {db_name} created successfully for {domain}", style="bold green")
    except Error as err:
        console.print(f"Error creating database: {err}", style="bold red")

def delete_database(domain, db_name, db_user):
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=get_mysql_root_password()
        )
        cursor = conn.cursor()
        
        cursor.execute(f"DROP DATABASE IF EXISTS {db_name}")
        cursor.execute(f"DROP USER IF EXISTS '{db_user}'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        
        conn.close()
        console.print(f"Database {db_name} deleted successfully for {domain}", style="bold green")
    except Error as err:
        console.print(f"Error deleting database: {err}", style="bold red")

def get_mysql_root_password():
    # In a real-world scenario, you'd want to securely store and retrieve this password
    return "your_mysql_root_password"

def backup_website(domain):
    backup_dir = os.path.join(BASE_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"{domain}_{timestamp}.tar.gz")
    
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add(os.path.join(BASE_DIR, 'sites', domain), arcname=domain)
    
    console.print(f"Backup created: {backup_file}", style="bold green")

def restore_website(backup_file, domain):
    site_dir = os.path.join(BASE_DIR, 'sites', domain)
    if os.path.exists(site_dir):
        shutil.rmtree(site_dir)
    
    with tarfile.open(backup_file, "r:gz") as tar:
        tar.extractall(path=os.path.join(BASE_DIR, 'sites'))
    
    console.print(f"Website {domain} restored from {backup_file}", style="bold green")
    rebuild(domain)

def add_custom_nginx_config(domain):
    config_path = os.path.join(BASE_DIR, 'nginx', f'{domain}_custom.conf')
    console.print("Enter your custom Nginx configuration. Press Ctrl+D when finished:", style="bold blue")
    custom_config = sys.stdin.read().strip()
    
    with open(config_path, 'w') as f:
        f.write(custom_config)
    
    console.print(f"Custom Nginx configuration added for {domain}", style="bold green")
    rebuild(domain)

def setup_goaccess(domain):
    goaccess_config = f"""
log-format COMBINED
log-file /var/log/nginx/{domain}.access.log
output /var/www/html/{domain}/stats/index.html
real-time-html true
ws-url wss://{domain}/stats/
"""
    config_path = os.path.join(BASE_DIR, 'goaccess', f'{domain}.conf')
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    with open(config_path, 'w') as f:
        f.write(goaccess_config)
    
    docker_compose['services']['goaccess'] = {
        'image': 'allinurl/goaccess',
        'volumes': [
            f'./goaccess:/etc/goaccess',
            f'./nginx/logs:/var/log/nginx',
            f'./sites/{domain}/stats:/var/www/html/{domain}/stats'
        ],
        'command': f'goaccess --config-file=/etc/goaccess/{domain}.conf',
        'restart': 'always',
    }
    
    with open(os.path.join(BASE_DIR, 'docker-compose.yml'), 'w') as f:
        yaml.dump(docker_compose, f)
    
    console.print(f"GoAccess statistics set up for {domain}", style="bold green")
    rebuild(domain)

def setup_rebuild(domain):
    """Set up automatic rebuilding for a domain."""
    cron_file = os.path.join(BASE_DIR, 'cron', f'{domain}_rebuild.sh')
    os.makedirs(os.path.dirname(cron_file), exist_ok=True)

    cron_content = f"""#!/bin/bash
cd {BASE_DIR}
docker-compose up -d --build
docker-compose exec -T nginx nginx -s reload
"""

    with open(cron_file, 'w') as f:
        f.write(cron_content)
    
    os.chmod(cron_file, 0o755)  # Make the script executable

    cron_schedule = "0 4 * * *"  # Run at 4 AM every day
    cron_command = f"{cron_file} >> {BASE_DIR}/logs/{domain}_rebuild.log 2>&1"

    if os.name == 'posix':  # Unix-like systems
        try:
            import crontab
            cron = crontab.CronTab(user=True)
            job = cron.new(command=cron_command)
            job.setall(cron_schedule)
            cron.write()
            console.print(f"Automatic rebuild set up for {domain}", style="bold green")
        except ImportError:
            console.print("python-crontab is not installed. To set up automatic rebuilds, please run:", style="bold yellow")
            console.print(f"pip install python-crontab", style="bold blue")
            console.print(f"Then, to manually set up the cron job, add the following line to your crontab:", style="bold blue")
            console.print(f"{cron_schedule} {cron_command}", style="bold blue")
    else:  # Windows systems
        console.print("Automatic rebuild setup is not supported on Windows.", style="bold yellow")
        console.print("To schedule automatic rebuilds, use Windows Task Scheduler:", style="bold blue")
        console.print(f"1. Open Task Scheduler", style="bold blue")
        console.print(f"2. Create a new task", style="bold blue")
        console.print(f"3. Set the trigger to run daily at 4:00 AM", style="bold blue")
        console.print(f"4. Set the action to run the following command:", style="bold blue")
        console.print(f"   {sys.executable} {cron_file}", style="bold blue")

    # Add the domain to the list of domains to be rebuilt
    rebuild_list_file = os.path.join(BASE_DIR, 'rebuild_list.txt')
    with open(rebuild_list_file, 'a') as f:
        f.write(f"{domain}\n")

    console.print(f"Added {domain} to the rebuild list", style="bold green")

def setup_ftp_access(domain, username, password):
    ftp_users_file = os.path.join(BASE_DIR, 'ftp', 'users.conf')
    os.makedirs(os.path.dirname(ftp_users_file), exist_ok=True)
    
    with open(ftp_users_file, 'a') as f:
        f.write(f"{username}:{password}:{BASE_DIR}/sites/{domain}\n")
    
    if 'ftp' not in docker_compose['services']:
        docker_compose['services']['ftp'] = {
            'image': 'bogem/ftp',
            'ports': ['21:21', '30000-30009:30000-30009'],
            'volumes': [
                './ftp/users.conf:/etc/pure-ftpd/passwd/pureftpd.passwd',
                './sites:/home/ftpusers'
            ],
            'environment': [
                'FTP_USER_NAME=admin',
                'FTP_USER_PASS=admin',
                'FTP_USER_HOME=/home/ftpusers'
            ],
            'restart': 'always',
        }
    
    with open(os.path.join(BASE_DIR, 'docker-compose.yml'), 'w') as f:
        yaml.dump(docker_compose, f)
    
    console.print(f"FTP access set up for {domain}", style="bold green")
    rebuild(domain)

def create_staging_environment(domain):
    staging_domain = f"staging.{domain}"
    site_dir = os.path.join(BASE_DIR, 'sites', domain)
    staging_dir = os.path.join(BASE_DIR, 'sites', staging_domain)
    
    shutil.copytree(site_dir, staging_dir)
    create_nginx_conf(staging_domain, ssl=False)
    
    console.print(f"Staging environment created for {domain} at {staging_domain}", style="bold green")
    rebuild(staging_domain)

def promote_staging_to_production(domain):
    staging_domain = f"staging.{domain}"
    site_dir = os.path.join(BASE_DIR, 'sites', domain)
    staging_dir = os.path.join(BASE_DIR, 'sites', staging_domain)
    
    shutil.rmtree(site_dir)
    shutil.move(staging_dir, site_dir)
    
    console.print(f"Staging environment promoted to production for {domain}", style="bold green")
    rebuild(domain)

def setup_wildcard_ssl(domain):
    console.print("Wildcard SSL setup is not implemented in this version.", style="yellow")

def setup_redis():
    docker_compose['services']['redis'] = {
        'image': 'redis:alpine',
        'restart': 'always',
    }
    
    with open(os.path.join(BASE_DIR, 'docker-compose.yml'), 'w') as f:
        yaml.dump(docker_compose, f)
    
    console.print("Redis set up successfully", style="bold green")

def setup_cdn(domain):
    console.print("To set up a CDN, you'll need to sign up with a CDN provider like Cloudflare or StackPath.", style="bold yellow")
    console.print(f"Once you've signed up, update your domain's nameservers to those provided by your CDN.", style="bold yellow")
    console.print(f"Then, configure the CDN to point to your origin server at {domain}", style="bold yellow")
    
    cdn_provider = inquirer.text(message="Enter your CDN provider name (e.g., Cloudflare)")
    console.print(f"CDN setup instructions for {domain} with {cdn_provider} provided", style="bold green")

def setup_alerts(email):
    console.print("Alert setup is not implemented in this version.", style="yellow")

def add_server(hostname, ip_address, ssh_key_path):
    servers_file = os.path.join(BASE_DIR, 'servers.yml')
    if os.path.exists(servers_file):
        with open(servers_file, 'r') as f:
            servers = yaml.safe_load(f)
    else:
        servers = {}
    
    servers[hostname] = {
        'ip_address': ip_address,
        'ssh_key_path': ssh_key_path
    }
    
    with open(servers_file, 'w') as f:
        yaml.dump(servers, f)
    
    console.print(f"Server {hostname} added successfully", style="bold green")

def remove_server(hostname):
    servers_file = os.path.join(BASE_DIR, 'servers.yml')
    if os.path.exists(servers_file):
        with open(servers_file, 'r') as f:
            servers = yaml.safe_load(f)
        
        if hostname in servers:
            del servers[hostname]
            with open(servers_file, 'w') as f:
                yaml.dump(servers, f)
            console.print(f"Server {hostname} removed successfully", style="bold green")
        else:
            console.print(f"Server {hostname} not found", style="bold red")
    else:
        console.print("No servers configured", style="bold yellow")

def list_servers():
    servers_file = os.path.join(BASE_DIR, 'servers.yml')
    if os.path.exists(servers_file):
        with open(servers_file, 'r') as f:
            servers = yaml.safe_load(f)
        
        console.print("Configured servers:", style="bold blue")
        for hostname, details in servers.items():
            console.print(f"  {hostname}: {details['ip_address']}")
    else:
        console.print("No servers configured", style="bold yellow")

def pull_docker_image(image_name):
    try:
        client = docker.from_env()
        console.print(f"Pulling Docker image: {image_name}", style="bold blue")
        image = client.images.pull(image_name)
        console.print(f"Successfully pulled {image.tags[0]}", style="bold green")
    except docker.errors.ImageNotFound:
        console.print(f"Image {image_name} not found", style="bold red")
    except docker.errors.APIError as e:
        console.print(f"Error pulling image: {e}", style="bold red")

def list_docker_images():
    try:
        client = docker.from_env()
        images = client.images.list()
        console.print("Docker images:", style="bold blue")
        for image in images:
            console.print(f"  {image.tags[0] if image.tags else image.id[:12]}")
    except docker.errors.APIError as e:
        console.print(f"Error listing images: {e}", style="bold red")

def remove_docker_image(image_name):
    try:
        client = docker.from_env()
        console.print(f"Removing Docker image: {image_name}", style="bold blue")
        client.images.remove(image_name)
        console.print(f"Successfully removed {image_name}", style="bold green")
    except docker.errors.ImageNotFound:
        console.print(f"Image {image_name} not found", style="bold red")
    except docker.errors.APIError as e:
        console.print(f"Error removing image: {e}", style="bold red")

def load_plugins():
    plugins = {}
    plugin_dir = os.path.join(BASE_DIR, 'plugins')
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir)
    
    for filename in os.listdir(plugin_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]
            try:
                module = __import__(f'plugins.{module_name}', fromlist=['register_plugin'])
                if hasattr(module, 'register_plugin'):
                    plugins[module_name] = module.register_plugin()
                    console.print(f"Loaded plugin: {module_name}", style="bold green")
            except ImportError as e:
                console.print(f"Error loading plugin {module_name}: {e}", style="bold red")
    
    return plugins

def run_plugin(plugin_name, plugins):
    if plugin_name in plugins:
        try:
            plugins[plugin_name]()
        except Exception as e:
            console.print(f"Error running plugin {plugin_name}: {e}", style="bold red")
    else:
        console.print(f"Plugin {plugin_name} not found", style="bold red")

def setup(force=False):
    """Set up Glacier and install prerequisites"""
    if force or inquirer.confirm(message="Force reinstallation of prerequisites?", default=False):
        with console.status("[bold green]Installing prerequisites...") as status:
            install_prerequisites()
        console.print("Prerequisites installed successfully.", style="bold green")
    
    os.makedirs(os.path.join(BASE_DIR, 'nginx'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'sites'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'certs'), exist_ok=True)

    global docker_compose
    docker_compose = {
        'version': '3',
        'services': {
            'nginx': {
                'image': 'nginx:latest',
                'ports': ['80:80', '443:443'],
                'volumes': [
                    './nginx:/etc/nginx/conf.d',
                    './sites:/var/www/html',
                    './certs:/etc/letsencrypt',
                    './logs/nginx:/var/log/nginx'
                ],
                'depends_on': ['php7.4', 'php8.0', 'php8.1', 'php8.2', 'php8.3'],
                'restart': 'always',
            }
        }
    }

    setup_php_containers()
    setup_ssl_renewal()
    setup_fail2ban()
    setup_ufw_firewall()
    setup_monitoring()

    with open(os.path.join(BASE_DIR, 'docker-compose.yml'), 'w') as f:
        yaml.dump(docker_compose, f)

    console.print("Glacier setup completed successfully.", style="bold green")

def main():
    setup()
    plugins = load_plugins()

    while True:
        answers = inquirer.prompt([
            inquirer.List('action',
                          message="What would you like to do?",
                          choices=[
                              'Create website',
                              'Rebuild website',
                              'Create database',
                              'Delete database',
                              'Backup website',
                              'Restore website',
                              'Add custom Nginx config',
                              'Setup website statistics',
                              'Setup FTP access',
                              'Create staging environment',
                              'Promote staging to production',
                              'Setup wildcard SSL',
                              'Setup Redis',
                              'Setup CDN',
                              'Setup monitoring',
                              'Setup alerts',
                              'Add server',
                              'Remove server',
                              'List servers',
                              'Pull Docker image',
                              'List Docker images',
                              'Remove Docker image',
                              'Run plugin',
                              'Exit'
                          ])
        ])

        if answers['action'] == 'Create website':
            domain = inquirer.text(message="Enter the domain name")
            git = inquirer.text(message="Enter the Git repository URL (optional)")
            skip_ssl = inquirer.confirm(message="Skip SSL setup?", default=False)
            create(domain, git, skip_ssl)
        elif answers['action'] == 'Rebuild website':
            domain = inquirer.text(message="Enter the domain name")
            git = inquirer.text(message="Enter the Git repository URL (optional)")
            reconfigure_ssl = inquirer.confirm(message="Reconfigure SSL?", default=False)
            rebuild(domain, git, reconfigure_ssl)
        elif answers['action'] == 'Create database':
            domain = inquirer.text(message="Enter the domain name")
            db_name = inquirer.text(message="Enter the database name")
            db_user = inquirer.text(message="Enter the database user")
            db_password = inquirer.password(message="Enter the database password")
            create_database(domain, db_name, db_user, db_password)
        elif answers['action'] == 'Delete database':
            domain = inquirer.text(message="Enter the domain name")
            db_name = inquirer.text(message="Enter the database name")
            db_user = inquirer.text(message="Enter the database user")
            delete_database(domain, db_name, db_user)
        elif answers['action'] == 'Backup website':
            domain = inquirer.text(message="Enter the domain name to backup")
            backup_website(domain)
        elif answers['action'] == 'Restore website':
            backup_file = inquirer.text(message="Enter the backup file path")
            domain = inquirer.text(message="Enter the domain name to restore")
            restore_website(backup_file, domain)
        elif answers['action'] == 'Add custom Nginx config':
            domain = inquirer.text(message="Enter the domain name")
            add_custom_nginx_config(domain)
        elif answers['action'] == 'Setup website statistics':
            domain = inquirer.text(message="Enter the domain name")
            setup_goaccess(domain)
        elif answers['action'] == 'Setup FTP access':
            domain = inquirer.text(message="Enter the domain name")
            username = inquirer.text(message="Enter the FTP username")
            password = inquirer.password(message="Enter the FTP password")
            setup_ftp_access(domain, username, password)
        elif answers['action'] == 'Create staging environment':
            domain = inquirer.text(message="Enter the domain name")
            create_staging_environment(domain)
        elif answers['action'] == 'Promote staging to production':
            domain = inquirer.text(message="Enter the domain name")
            promote_staging_to_production(domain)
        elif answers['action'] == 'Setup wildcard SSL':
            domain = inquirer.text(message="Enter the domain name")
            setup_wildcard_ssl(domain)
        elif answers['action'] == 'Setup Redis':
            setup_redis()
        elif answers['action'] == 'Setup CDN':
            domain = inquirer.text(message="Enter the domain name")
            setup_cdn(domain)
        elif answers['action'] == 'Setup monitoring':
            setup_monitoring()
        elif answers['action'] == 'Setup alerts':
            email = inquirer.text(message="Enter the email address for alerts")
            setup_alerts(email)
        elif answers['action'] == 'Add server':
            hostname = inquirer.text(message="Enter the server hostname")
            ip_address = inquirer.text(message="Enter the server IP address")
            ssh_key_path = inquirer.text(message="Enter the path to the SSH key")
            add_server(hostname, ip_address, ssh_key_path)
        elif answers['action'] == 'Remove server':
            hostname = inquirer.text(message="Enter the server hostname to remove")
            remove_server(hostname)
        elif answers['action'] == 'List servers':
            list_servers()
        elif answers['action'] == 'Pull Docker image':
            image_name = inquirer.text(message="Enter the Docker image name to pull")
            pull_docker_image(image_name)
        elif answers['action'] == 'List Docker images':
            list_docker_images()
        elif answers['action'] == 'Remove Docker image':
            image_name = inquirer.text(message="Enter the Docker image name to remove")
            remove_docker_image(image_name)
        elif answers['action'] == 'Run plugin':
            plugin_choices = list(plugins.keys())
            if plugin_choices:
                plugin_name = inquirer.list_input("Select a plugin to run:", choices=plugin_choices)
                run_plugin(plugin_name, plugins)
            else:
                console.print("No plugins available", style="bold yellow")
        elif answers['action'] == 'Exit':
            break

if __name__ == "__main__":
    main()