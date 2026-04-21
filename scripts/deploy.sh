#!/bin/bash
# Automation according to the "Automatic Installation Script" section

# 0. Defining the project path
PROJECT_ROOT=$(pwd)
echo "Deploying from: $PROJECT_ROOT"

# 1. Installing packages
sudo apt update
sudo apt install -y python3-pip postgresql nginx

# 2. Creating system users
# 'student' and 'teacher' are needed for checking the work by the instructor
sudo useradd -m -G sudo student && echo "student:12345678" | sudo chpasswd
sudo useradd -m -G sudo teacher && echo "teacher:12345678" | sudo chpasswd
# 'app' - system user for safe code execution
sudo useradd -r -s /bin/false app
# 'operator' - for limited management (start/stop)
sudo useradd -m operator && echo "operator:12345678" | sudo chpasswd

# 3. Database (PostgreSQL according to V2=2)
sudo -u postgres psql -c "CREATE DATABASE task_db;"
sudo -u postgres psql -c "CREATE USER app_user WITH PASSWORD 'secure_pass';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE task_db TO app_user;"

# 4. Configuration and Gradebook
sudo mkdir -p /etc/mywebapp
echo "database_url: 'postgresql://app_user:secure_pass@localhost/task_db'" | sudo tee /etc/mywebapp/config.yaml
echo "3697" | sudo tee /home/student/gradebook

# 5. Permissions for operator (sudoers)
# Allow operator ONLY to restart the service and nginx
echo "operator ALL=(ALL) NOPASSWD: /usr/bin/systemctl * mywebapp, /usr/sbin/nginx -s reload" | sudo tee /etc/sudoers.d/operator

# 6. Locking the default user (e.g., 'ubuntu' or 'user')
# Warning: make sure you can already log in as student!
# sudo passwd -l ubuntu

# 7. Starting the service
# Update the working directory in the unit before copying
# On macOS sed -i requires an argument for backup, but this script is for Linux
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_ROOT|" "$PROJECT_ROOT/config/mywebapp.service"

sudo cp "$PROJECT_ROOT/config/mywebapp.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mywebapp