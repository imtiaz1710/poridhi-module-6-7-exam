# AWS Pulumi Hands-On Exam

Infrastructure as Code project using Pulumi (Python) to create secure AWS infrastructure with VPC, bastion host, private EC2 instance, and MySQL database.

## Quick Setup

1. **Clone and Install**
```bash
git clone https://github.com/imtiaz1710/poridhi-module-6-7-exam
cd aws-pulumi-exam
pip install pulumi pulumi-aws
```

2. **Configure**
```bash
pulumi stack init dev
cp Pulumi.dev.yaml.example Pulumi.dev.yaml
```

Edit `Pulumi.dev.yaml` accordingly:
```yaml
config:
  aws:region: ap-southeast-1
  project:sshPublicKey: "your-ssh-public-key"
  project:myPublicIP: "x.x.x.x/32"
  project:mysqlPassword: "secure-password"
```

3. **Deploy**
```bash
pulumi up
```

## Architecture

- **VPC**: 10.0.0.0/16 with public (10.0.1.0/24) and private (10.0.2.0/24) subnets
- **Bastion Host**: Public EC2 with hardened SSH access
- **Private Instance**: EC2 in private subnet with MySQL
- **Security**: Proper security groups and NAT Gateway for egress

## Key Commands

```bash
# Deploy infrastructure
pulumi up

# View outputs
pulumi stack output --json

# SSH to bastion
ssh ops@$(pulumi stack output bastionPublicIp)

# SSH to private instance via bastion
ssh -J ops@$(pulumi stack output bastionPublicIp) ec2-user@$(pulumi stack output privateInstanceIp)

# Test MySQL from bastion
mysql -h $(pulumi stack output privateInstanceIp) -u appuser -p

# Destroy infrastructure
pulumi destroy
```

## Project Structure

```
├── __main__.py                # Main Pulumi code
├── Pulumi.yaml               # Project config
├── Pulumi.dev.yaml.example   # Config template
├── README.md                 # This file
└── screenshots/              # Evidence screenshots
```

## Security Groups

- **bastion-sg**: SSH (22) from your IP only
- **app-sg**: SSH (22) from bastion-sg only

**Note**: `Pulumi.dev.yaml` is gitignored for security.
