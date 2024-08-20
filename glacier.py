#!/usr/bin/env python3

import sys
import subprocess
import logging
import os
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

# Attempt to import required libraries, install if not present
try:
    import inquirer
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "inquirer", "rich"])
    import inquirer
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

# Initialize Rich console for formatted output
console = Console()

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
        "sudo apt update",
        "sudo apt install -y apt-transport-https ca-certificates curl software-properties-common",
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg",
        "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null",
        "sudo apt update",
        "sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin python3-pip certbot",
        "sudo systemctl start docker",
        "sudo systemctl enable docker",
        "sudo usermod -aG docker $USER",
        "pip3 install --upgrade pip",
        "pip3 install tqdm pyyaml gitpython flask dnspython requests cryptography"
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

def check_dns(domain):
    """Check if DNS is properly configured for the domain"""
    try:
        server_ip = requests.get('https://api.ipify.org').text
        domain_ip = socket.gethostbyname(domain)
        
        try:
            www_domain_ip = socket.gethostbyname(f"www.{domain}")
        except socket.gaierror:
            www_domain_ip = domain_ip

        return server_ip == domain_ip and (server_ip == www_domain_ip or www_domain_ip == domain_ip)
    except:
        return False

def parse_htaccess(htaccess_path):
    """Parse .htaccess file and convert rules to Nginx configuration"""
    nginx_rules = []
    with open(htaccess_path, 'r') as htaccess_file:
        for line in htaccess_file:
            line = line.strip()
            if line.startswith('RewriteRule'):
                parts = line.split()
                if len(parts) >= 4:
                    pattern = parts[1].strip('^$')
                    target = parts[2]
                    flags = parts[3] if len(parts) > 3 else ''
                    nginx_rule = f"rewrite ^{pattern}$ {target} {flags};"
                    nginx_rules.append(nginx_rule)
            elif line.startswith('RewriteCond'):
                # For simplicity, we'll skip RewriteCond for now
                # In a full implementation, you'd need to handle these as well
                pass
            elif line.startswith('Options'):
                if '-Indexes' in line:
                    nginx_rules.append("autoindex off;")
            # Add more translations as needed

    return nginx_rules

def find_htaccess_files(root_dir):
    """Find all .htaccess files in the given directory and its subdirectories"""
    htaccess_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if '.htaccess' in filenames:
            htaccess_files.append(os.path.join(dirpath, '.htaccess'))
    return htaccess_files

def create_nginx_conf(domain, ssl=False):
    """Create Nginx configuration for the given domain"""
    site_root = os.path.join(BASE_DIR, 'sites', domain)
    htaccess_files = find_htaccess_files(site_root)
    
    nginx_rules = []
    for htaccess_file in htaccess_files:
        relative_path = os.path.relpath(os.path.dirname(htaccess_file), site_root)
        location_path = f"/{relative_path}" if relative_path != '.' else '/'
        rules = parse_htaccess(htaccess_file)
        if rules:
            nginx_rules.append(f"location {location_path} {{")
            nginx_rules.extend(f"    {rule}" for rule in rules)
            nginx_rules.append("}")

    conf_content = f"""
server {{
    listen 80;
    server_name {domain} www.{domain};
    root /var/www/html/{domain};
    index index.php index.html index.htm;

    # Global rewrite rules
    location / {{
        try_files $uri $uri/ $uri.html /index.php?$query_string;
    }}

    # Remove .html extension
    if ($request_uri ~ ^/(.*)\.html$) {{
        return 301 /$1;
    }}

    # Redirect /index to /
    location = /index {{
        return 301 /;
    }}

    # Prevent directory listing
    autoindex off;

    # PHP handling
    location ~ \.php$ {{
        fastcgi_split_path_info ^(.+\.php)(/.+)$;
        fastcgi_pass php:9000;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param PATH_INFO $fastcgi_path_info;
    }}

    # Deny access to .htaccess files
    location ~ /\.ht {{
        deny all;
    }}

    # Custom error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
    location = /50x.html {{
        root /usr/share/nginx/html;
    }}

    # Translated .htaccess rules
    {chr(10).join(nginx_rules)}
"""

    if ssl:
        conf_content += f"""
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
"""

    conf_content += "}\n"

    nginx_conf_path = os.path.join(BASE_DIR, 'nginx', f'{domain}.conf')
    with open(nginx_conf_path, 'w') as f:
        f.write(conf_content)
    console.print(f"Created Nginx configuration for {domain} at {nginx_conf_path}", style="bold green")

def check_dns_txt_record(domain, expected_value):
    """Check if the DNS TXT record for the domain matches the expected value"""
    try:
        answers = dns.resolver.resolve(f'_acme-challenge.{domain}', 'TXT')
        for rdata in answers:
            if expected_value in str(rdata):
                return True
        return False
    except dns.exception.DNSException:
        return False

def setup_ssl(domain):
    """Set up SSL for the given domain using DNS authentication"""
    logger.info(f"Setting up SSL for {domain} using DNS authentication")
    
    # Generate a random value for DNS TXT record
    acme_challenge_value = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
    
    console.print(f"Please create a TXT record for _acme-challenge.{domain} with the following value:", style="bold yellow")
    console.print(f"\n{acme_challenge_value}\n", style="bold green")
    console.print("You have 5 minutes to create this DNS record.", style="bold yellow")
    console.print("The script will automatically continue after 5 minutes, or you can press Enter to continue sooner.", style="italic")
    console.print("You can use Ctrl+C to copy the text without interrupting the process.", style="italic")

    def signal_handler(sig, frame):
        console.print("\nCtrl+C pressed. You can copy the text. The timer is still running.", style="bold yellow")

    # Set up the signal handler
    original_handler = signal.signal(signal.SIGINT, signal_handler)

    try:
        # Wait for user input or timeout after 5 minutes
        timeout = time.time() + 300  # 5 minutes from now
        while True:
            try:
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    line = input()
                    break
                if time.time() > timeout:
                    console.print("5 minutes have passed. Continuing automatically.", style="bold yellow")
                    break
            except IOError:
                pass  # This handles the IOError that can occur when select is interrupted
    finally:
        # Restore the original signal handler
        signal.signal(signal.SIGINT, original_handler)

    # Check if the DNS record has propagated
    console.print("Checking DNS propagation...", style="bold blue")
    for _ in range(10):  # Try for about 5 minutes
        if check_dns_txt_record(domain, acme_challenge_value):
            console.print("DNS record found. Proceeding with SSL certificate issuance.", style="bold green")
            break
        console.print("DNS record not found yet. Waiting 30 seconds before checking again...", style="yellow")
        time.sleep(30)
    else:
        console.print("DNS record not found after 5 minutes. Please check your DNS configuration and try again.", style="bold red")
        return

    # Run certbot command with DNS authentication
    certbot_command = f"sudo certbot certonly -v --manual --preferred-challenges=dns " \
                      f"-d {domain} -d www.{domain} --agree-tos " \
                      f"--cert-name {domain} " \
                      f"--manual-auth-hook 'echo {acme_challenge_value}' " \
                      f"--manual-cleanup-hook 'echo Cleanup complete' --non-interactive"

    try:
        result = subprocess.run(certbot_command, shell=True, check=True, capture_output=True, text=True)
        console.print(result.stdout, style="green")
        logger.debug(result.stderr)

        cert_path = os.path.join(BASE_DIR, 'certs', 'live', domain)
        os.makedirs(cert_path, exist_ok=True)
        shutil.copy(f'/etc/letsencrypt/live/{domain}/privkey.pem', os.path.join(cert_path, 'privkey.pem'))
        shutil.copy(f'/etc/letsencrypt/live/{domain}/fullchain.pem', os.path.join(cert_path, 'fullchain.pem'))

        create_nginx_conf(domain, ssl=True)
        run_command(f'cd {BASE_DIR} && docker-compose restart nginx')
        console.print(f"SSL set up successfully for {domain}", style="bold green")
    except subprocess.CalledProcessError as e:
        console.print(f"Error obtaining SSL certificate: {e.stderr}", style="bold red")
        logger.debug(f"Certbot command output: {e.stdout}")
        console.print("Setting up website without SSL. You can try to set up SSL later using the 'rebuild' command.", style="yellow")
        create_nginx_conf(domain, ssl=False)
        run_command(f'cd {BASE_DIR} && docker-compose restart nginx')

    console.print(f"You can now remove the TXT record for _acme-challenge.{domain}", style="bold yellow")

def setup(force=False):
    """Set up Glacier and install prerequisites"""
    if force or inquirer.confirm(message="Force reinstallation of prerequisites?", default=False):
        with console.status("[bold green]Installing prerequisites...") as status:
            install_prerequisites()
        console.print("Prerequisites installed successfully.", style="bold green")
    
    os.makedirs(os.path.join(BASE_DIR, 'nginx'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'sites'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'certs'), exist_ok=True)

    docker_compose = {
        'version': '3',
        'services': {
            'nginx': {
                'image': 'nginx:latest',
                'ports': ['80:80', '443:443'],
                'volumes': [
                    './nginx:/etc/nginx/conf.d',
                    './sites:/var/www/html',
                    './certs:/etc/letsencrypt'
                ],
                'restart': 'always',
            },
            'php': {
                'build': {
                    'context': '.',
                    'dockerfile': 'Dockerfile-php'
                },
                'volumes': [
                    './sites:/var/www/html'
                ],
                'restart': 'always',
            }
        }
    }

    with open(os.path.join(BASE_DIR, 'docker-compose.yml'), 'w') as f:
        yaml.dump(docker_compose, f)

    with open(os.path.join(BASE_DIR, 'Dockerfile-php'), 'w') as f:
        f.write("""
FROM php:7.4-fpm

RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) gd

RUN docker-php-ext-install pdo pdo_mysql
""")

    console.print("Glacier setup completed successfully.", style="bold green")
    console.print("You can now create websites using the 'create' command.", style="bold blue")

def create(domain, git=None, skip_ssl=False):
    """Create a new website"""
    with console.status(f"[bold green]Creating website for {domain}...") as status:
        site_dir = os.path.join(BASE_DIR, 'sites', domain)
        os.makedirs(site_dir, exist_ok=True)
        
        if git:
            console.print(f"Cloning repository for {domain}...", style="bold blue")
            run_command(f'git clone {git} {site_dir}')
        else:
            with open(os.path.join(site_dir, 'index.php'), 'w') as f:
                f.write('<?php phpinfo(); ?>')
        
        create_nginx_conf(domain, ssl=False)
        
        console.print(f"Website {domain} created successfully.", style="bold green")
        console.print("Starting Glacier services...", style="bold blue")
        run_command(f'cd {BASE_DIR} && docker-compose up -d --build')
        
        if not skip_ssl:
            console.print("Proceeding with SSL setup.", style="bold blue")
            setup_ssl(domain)
        else:
            console.print("Skipping SSL setup as requested.", style="yellow")

def rebuild(domain, git=None, reconfigure_ssl=False, force=False):
    """Rebuild an existing website"""
    with console.status(f"[bold green]Rebuilding website {domain}...") as status:
        site_dir = os.path.join(BASE_DIR, 'sites', domain)
        
        if not os.path.exists(site_dir):
            console.print(f"Error: Website {domain} does not exist.", style="bold red")
            return
        
        if git:
            console.print(f"Updating repository for {domain}...", style="bold blue")
            run_command(f'cd {site_dir} && git pull')
        
        console.print("Rebuilding PHP container...", style="bold blue")
        run_command(f'cd {BASE_DIR} && docker-compose build php')
        run_command(f'cd {BASE_DIR} && docker-compose up -d --no-deps php')
        
        if reconfigure_ssl:
            setup_ssl(domain)
        else:
            ssl_enabled = os.path.exists(os.path.join(BASE_DIR, 'certs', 'live', domain, 'fullchain.pem'))
            create_nginx_conf(domain, ssl=ssl_enabled)
        
        run_command(f'cd {BASE_DIR} && docker-compose restart nginx')
    
    console.print(f"Website {domain} rebuilt successfully.", style="bold green")

def start():
    """Start Glacier services"""
    with console.status("[bold green]Starting Glacier services...") as status:
        run_command(f'cd {BASE_DIR} && docker-compose up -d')
    console.print("Glacier services started.", style="bold green")

def stop():
    """Stop Glacier services"""
    with console.status("[bold green]Stopping Glacier services...") as status:
        run_command(f'cd {BASE_DIR} && docker-compose down')
    console.print("Glacier services stopped.", style="bold green")

def logs(domain):
    """View logs for a specific website"""
    console.print(f"Displaying logs for {domain}:", style="bold blue")
    run_command(f'cd {BASE_DIR} && docker-compose logs --tail=100 -f nginx php')

def delete(domain, force=False):
    """Delete an existing website"""
    if force or inquirer.confirm(f"Are you sure you want to delete {domain}?", default=False):
        with console.status(f"[bold red]Deleting website {domain}...") as status:
            site_dir = os.path.join(BASE_DIR, 'sites', domain)
            nginx_conf = os.path.join(BASE_DIR, 'nginx', f'{domain}.conf')
            cert_dir = os.path.join(BASE_DIR, 'certs', 'live', domain)
            
            if os.path.exists(site_dir):
                shutil.rmtree(site_dir)
            if os.path.exists(nginx_conf):
                os.remove(nginx_conf)
            if os.path.exists(cert_dir):
                shutil.rmtree(cert_dir)
            
            run_command(f'cd {BASE_DIR} && docker-compose restart nginx')
        console.print(f"Website {domain} deleted successfully.", style="bold green")

def install_php_extension(php_extension):
    """Install a PHP extension"""
    with console.status(f"[bold green]Installing PHP extension: {php_extension}...") as status:
        dockerfile_path = os.path.join(BASE_DIR, 'Dockerfile-php')
        with open(dockerfile_path, 'a') as f:
            f.write(f"\nRUN docker-php-ext-install {php_extension}")
        
        run_command(f'cd {BASE_DIR} && docker-compose build php')
        run_command(f'cd {BASE_DIR} && docker-compose up -d --no-deps php')
    console.print(f"PHP extension {php_extension} installed successfully.", style="bold green")

def uninstall(force=False):
    """Uninstall Glacier"""
    if force or inquirer.confirm("Are you sure you want to uninstall Glacier? This will remove all websites and data.", default=False):
        with console.status("[bold red]Uninstalling Glacier...") as status:
            run_command(f'cd {BASE_DIR} && docker-compose down -v')
            shutil.rmtree(os.path.join(BASE_DIR, 'nginx'), ignore_errors=True)
            shutil.rmtree(os.path.join(BASE_DIR, 'sites'), ignore_errors=True)
            shutil.rmtree(os.path.join(BASE_DIR, 'certs'), ignore_errors=True)
            os.remove(os.path.join(BASE_DIR, 'docker-compose.yml'))
            os.remove(os.path.join(BASE_DIR, 'Dockerfile-php'))
        console.print("Glacier has been uninstalled successfully.", style="bold green")

def menu():
    """Interactive menu for Glacier operations"""
    while True:
        console.print(Panel(Text("Glacier: Easy Website Management", style="bold magenta")), justify="center")
        
        questions = [
            inquirer.List('action',
                          message="What would you like to do?",
                          choices=[
                              ('Setup Glacier', 'setup'),
                              ('Create a new website', 'create'),
                              ('Rebuild an existing website', 'rebuild'),
                              ('Start Glacier services', 'start'),
                              ('Stop Glacier services', 'stop'),
                              ('View website logs', 'logs'),
                              ('Delete a website', 'delete'),
                              ('Install PHP extension', 'install_php_extension'),
                              ('Uninstall Glacier', 'uninstall'),
                              ('Exit', 'exit')
                          ],
                          ),
        ]
        answers = inquirer.prompt(questions)
        
        if answers['action'] == 'exit':
            console.print("Thank you for using Glacier!", style="bold green")
            break
        elif answers['action'] == 'setup':
            setup()
        elif answers['action'] in ['create', 'rebuild', 'logs', 'delete']:
            domain = inquirer.text(message="Enter the domain name")
            if answers['action'] == 'create':
                git = inquirer.text(message="Enter Git repository URL (optional)")
                skip_ssl = inquirer.confirm(message="Skip SSL setup?", default=False)
                create(domain, git, skip_ssl)
            elif answers['action'] == 'rebuild':
                git = inquirer.text(message="Enter Git repository URL to update from (optional)")
                reconfigure_ssl = inquirer.confirm(message="Reconfigure SSL?", default=False)
                force = inquirer.confirm(message="Force rebuild without confirmation?", default=False)
                rebuild(domain, git, reconfigure_ssl, force)
            elif answers['action'] == 'logs':
                logs(domain)
            elif answers['action'] == 'delete':
                force = inquirer.confirm(message="Force deletion without confirmation?", default=False)
                delete(domain, force)
        elif answers['action'] == 'install_php_extension':
            extension = inquirer.text(message="Enter the PHP extension name")
            install_php_extension(extension)
        elif answers['action'] == 'uninstall':
            force = inquirer.confirm(message="Force uninstallation without confirmation?", default=False)
            uninstall(force)
        else:
            globals()[answers['action']]()
        
        console.print("\nPress Enter to continue...", style="italic")
        input()
        console.clear()

if __name__ == '__main__':
    menu()