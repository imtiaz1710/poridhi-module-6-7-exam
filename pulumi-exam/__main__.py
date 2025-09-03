"""An AWS Python Pulumi program"""
import pulumi
import pulumi_aws as aws
import base64

config = pulumi.Config()
public_ip = config.require("publicIp") 


vpc = aws.ec2.Vpc("poridhi-vpc",
                  cidr_block="10.0.0.0/16",
                  tags={
                      "Name": "poridhi-vpc"
                  })

pulumi.export("vpc_id", vpc.id)

public_subnet = aws.ec2.Subnet("public-subnet",
                               vpc_id = vpc.id,
                               cidr_block="10.0.1.0/24",
                               availability_zone="ap-southeast-1a",
                               map_public_ip_on_launch=True,
                               tags={
                                   "Name":"public-subnet"
                               })

pulumi.export("public_subnet_id", public_subnet.id)

igw = aws.ec2.InternetGateway("internet-gateway",
                              vpc_id=vpc.id,
                              tags={
                                  "Name":"igw"
                              })

pulumi.export("igw_id", igw.id)

public_route_table = aws.ec2.RouteTable("public-route-table",
                                        vpc_id=vpc.id,
                                        tags={
                                            "Name":"rt-public"
                                        })

public_route = aws.ec2.Route("igw-route",
                      route_table_id=public_route_table.id,
                      destination_cidr_block="0.0.0.0/0",
                      gateway_id=igw.id
                      )
public_route_table_association = aws.ec2.RouteTableAssociation("public_route_table_association",
                                                               subnet_id=public_subnet.id,
                                                               route_table_id=public_route_table.id
                                                               )

pulumi.export("public_route_table_id", public_route_table.id)

private_subnet = aws.ec2.Subnet("private-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.2.0/24",
    availability_zone="ap-southeast-1a",
    tags={
        "Name": "my-private-subnet"
    }
)

pulumi.export("private_subnet_id", private_subnet.id)

eip = aws.ec2.Eip("nat-eip")
pulumi.export("eip_public_ip", eip.public_ip)

nat_gateway = aws.ec2.NatGateway("nat-gateway",
                                    allocation_id=eip.id,
                                    subnet_id=public_subnet.id,
                                    tags={
                                        "Name": "nat-gateway"
                                    }
                                )
pulumi.export("nat_gateway_id", nat_gateway.id)

private_route_table = aws.ec2.RouteTable("private-route-table",
                                         vpc_id=vpc.id,
                                         tags={
                                             "Name": "rt-private"
                                         })
private_route = aws.ec2.Route("nat-route",
                              route_table_id=private_route_table.id,
                              destination_cidr_block="0.0.0.0/0",
                              nat_gateway_id=nat_gateway.id
                              )
private_route_table_association = aws.ec2.RouteTableAssociation("private_route_table_association",
                                                               subnet_id=private_subnet.id,
                                                               route_table_id=private_route_table.id
                                                               )
pulumi.export("private_route_table_id", private_route_table.id)


bastion_sg = aws.ec2.SecurityGroup("bastion-sg",
                                                name="bastion-sg",
                                                description="Security group for bastion host - SSH access only from my IP",
                                                vpc_id=vpc.id,
                                                ingress=[
                                                    aws.ec2.SecurityGroupIngressArgs(
                                                        description="SSH from my public IP only",
                                                        protocol="tcp",
                                                        from_port=22,
                                                        to_port=22,
                                                        cidr_blocks=[public_ip],  # Only your public IP
                                                    )
                                                ],
                                                egress=[
                                                    aws.ec2.SecurityGroupEgressArgs(
                                                        description="All outbound traffic",
                                                        protocol="-1",
                                                        from_port=0,
                                                        to_port=0,
                                                        cidr_blocks=["0.0.0.0/0"]
                                                    )
                                                ],
                                                tags={
                                                    "Name": "bastion-sg",
                                                    "Purpose": "SSH access to bastion host"
                                                }
                                            )

pulumi.export("public_sg_id", bastion_sg.id)

ssh_public_key = pulumi.Config().require("sshPublicKey")

bastion_user_data = f"""#!/bin/bash
set -e

# Update system
apt-get update -y
apt-get upgrade -y

# Create non-root sudo user 'ops' with SSH key injected from Pulumi config
useradd -m -s /bin/bash ops
usermod -aG sudo ops

# Setup passwordless sudo for ops
echo "ops ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ops
chmod 440 /etc/sudoers.d/ops

# Setup SSH for ops user
mkdir -p /home/ops/.ssh
chmod 700 /home/ops/.ssh

# Inject SSH key from project:sshPublicKey
echo "{ssh_public_key.strip()}" > /home/ops/.ssh/authorized_keys
chmod 600 /home/ops/.ssh/authorized_keys
chown -R ops:ops /home/ops/.ssh

# Disable root SSH login and password authentication in sshd_config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Disable root login
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# Disable password authentication  
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Ensure key-based authentication is enabled
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Additional hardening
cat >> /etc/ssh/sshd_config << 'SSHEOF'

# Security hardening additions
AllowUsers ops ubuntu
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
SSHEOF

# Restart SSH service
systemctl restart ssh

# Install useful tools for bastion operations
apt-get install -y mysql-client curl wget htop

# Log completion
echo "Ubuntu bastion hardening completed at $(date)" | tee -a /var/log/bastion-setup.log
"""

key_pair = aws.ec2.KeyPair(
    "bastion-keypair",
    key_name="bastion-keypair",
    public_key=ssh_public_key,
    tags={"Name": "bastion-keypair"}
)

ami_id = 'ami-0933f1385008d33c4'

# EC2 Instance in public subnet with public IPv4
bastion_instance = aws.ec2.Instance("bastion-host",
    ami=ami_id,
    instance_type="t2.micro",
    key_name=key_pair.key_name,
    vpc_security_group_ids=[bastion_sg.id],
    subnet_id=public_subnet.id,
    associate_public_ip_address=True,  # Required: public IPv4
    user_data=base64.b64encode(bastion_user_data.encode('utf-8')).decode('utf-8'),
    
    tags={
        "Name": "bastion-host",
        "Purpose": "SSH jump host"
    }
)


pulumi.export("bastion_instance_id", bastion_instance.id)
pulumi.export("bastion_public_ip", bastion_instance.public_ip)

# Security Group (app-sg): SSH and MySQL only from bastion-sg  
app_sg = aws.ec2.SecurityGroup("app-sg",
    name="app-sg",
    description="Security group for private app instance", 
    vpc_id=vpc.id,
    ingress=[
        {
            "description": "SSH from bastion security group only",
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "security_groups": [bastion_sg.id],  # Use security_groups instead
        },
        {
            "description": "MySQL from bastion security group", 
            "protocol": "tcp",
            "from_port": 3306,
            "to_port": 3306,
            "security_groups": [bastion_sg.id],
        }
    ],
    egress=[
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"]
        }
    ],
    tags={"Name": "app-sg"}
)

mysql_password = config.require_secret("mysqlPassword")  # MySQL password

private_user_data = f"""#!/bin/bash
set -e

# Update system
apt-get update -y
apt-get upgrade -y

# Install MySQL Server (community server)
export DEBIAN_FRONTEND=noninteractive
apt-get install -y mysql-server

# Start and enable MySQL service (survives reboot)
systemctl start mysql
systemctl enable mysql

# Get instance private IP
PRIVATE_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

# Configure MySQL to listen on 127.0.0.1 and the instance's private IP
cat > /etc/mysql/mysql.conf.d/custom.cnf << EOF
[mysqld]
bind-address = 0.0.0.0
EOF

# Restart MySQL to apply configuration
systemctl restart mysql

# Wait for MySQL to be ready
sleep 15

# Create database 'appdb' and user 'appuser' with generated password
mysql -u root << SQLEOF
CREATE DATABASE appdb;
CREATE USER 'appuser'@'localhost' IDENTIFIED BY '{mysql_password}';
CREATE USER 'appuser'@'%' IDENTIFIED BY '{mysql_password}';
GRANT ALL PRIVILEGES ON appdb.* TO 'appuser'@'localhost';
GRANT ALL PRIVILEGES ON appdb.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
SQLEOF

# Setup SSH for ubuntu user (default Ubuntu user)
mkdir -p /home/ubuntu/.ssh
echo "{ssh_public_key.strip()}" > /home/ubuntu/.ssh/authorized_keys
chmod 600 /home/ubuntu/.ssh/authorized_keys
chown -R ubuntu:ubuntu /home/ubuntu/.ssh

# Verify service is enabled and started
systemctl is-enabled mysql
systemctl is-active mysql

# Log completion
echo "MySQL installation and configuration completed at $(date)" >> /var/log/mysql-setup.log
echo "Database: appdb, User: appuser created successfully" >> /var/log/mysql-setup.log
echo "MySQL is listening on 0.0.0.0:3306" >> /var/log/mysql-setup.log
"""

private_instance = aws.ec2.Instance("private-app",
    ami=ami_id,
    instance_type="t2.micro",
    key_name=key_pair.key_name,
    vpc_security_group_ids=[app_sg.id],
    subnet_id=private_subnet.id,
    associate_public_ip_address=False,  # NO public IP - private subnet only
    user_data=base64.b64encode(private_user_data.encode('utf-8')).decode('utf-8'),
    tags={
        "Name": "private-app",
        "Role": "database",
        "Environment": "exam"
    }
)

pulumi.export("private_instance_id", private_instance.id)
pulumi.export("private_instance_ip", private_instance.private_ip)
