terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_vpc" "genesis" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "genesis-vpc"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.genesis.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "genesis-public-subnet"
  }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.genesis.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "us-east-1b"

  tags = {
    Name = "genesis-private-subnet-a"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.genesis.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "us-east-1c"

  tags = {
    Name = "genesis-private-subnet-b"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.genesis.id

  tags = {
    Name = "genesis-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.genesis.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "genesis-public-rt"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.genesis.id

  tags = {
    Name = "genesis-private-rt"
  }
}

resource "aws_route_table_association" "public_subnet" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_subnet_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_subnet_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "ec2_sg" {
  name        = "genesis-ec2-sg"
  description = "Allow HTTP from the internet"
  vpc_id      = aws_vpc.genesis.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "genesis-ec2-sg"
  }
}

resource "aws_security_group" "rds_sg" {
  name        = "genesis-rds-sg"
  description = "Allow PostgreSQL from EC2 only"
  vpc_id      = aws_vpc.genesis.id

  ingress {
    description     = "PostgreSQL from EC2"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_sg.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "genesis-rds-sg"
  }
}

resource "aws_db_subnet_group" "genesis" {
  name       = "genesis-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = {
    Name = "genesis-db-subnet-group"
  }
}

resource "aws_db_instance" "genesis" {
  identifier             = "genesis-db"
  engine                 = "postgres"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  db_name                = "genesisdb"
  username               = "genesis"
  password               = "GenesisPass123!"
  publicly_accessible    = false
  deletion_protection    = false
  skip_final_snapshot    = true
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.genesis.name

  tags = {
    Name = "genesis-db"
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_iam_role" "ec2_ssm_role" {
  name = "genesis-ec2-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_ssm_core" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "genesis-ec2-profile"
  role = aws_iam_role.ec2_ssm_role.name
}

resource "aws_instance" "genesis_api" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.ec2_sg.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  user_data_replace_on_change = true

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail

    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y nginx postgresql-client

    DB_HOST="${aws_db_instance.genesis.address}"
    DB_NAME="genesisdb"
    DB_USER="genesis"
    DB_PASS="GenesisPass123!"
    export PGPASSWORD="$DB_PASS"

    DB_JSON='{"db_status":"error","error":"query not executed"}'
    for i in $(seq 1 30); do
      if pg_isready -h "$DB_HOST" -p 5432 -U "$DB_USER" -d "$DB_NAME"; then
        DB_JSON=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT json_build_object('db_status','connected','database',current_database(),'db_user',current_user,'server_time',now())::text;") || true
        break
      fi
      sleep 10
    done

    if [ -z "$DB_JSON" ]; then
      DB_JSON='{"db_status":"error","error":"empty response from query"}'
    fi

    mkdir -p /var/www/project-genesis
    cat > /var/www/project-genesis/health.json << 'HEALTH'
    {"status":"healthy","service":"project-genesis-api"}
    HEALTH

    echo "$DB_JSON" > /var/www/project-genesis/db-check.json
    cat > /var/www/project-genesis/index.json << 'INDEX'
    {"message":"Project Genesis API is running"}
    INDEX

    cat > /etc/nginx/sites-available/project-genesis << 'NGINX'
    server {
      listen 80 default_server;
      server_name _;

      location = / {
        default_type application/json;
        alias /var/www/project-genesis/index.json;
      }

      location = /api/v1/health {
        default_type application/json;
        alias /var/www/project-genesis/health.json;
      }

      location = /api/v1/db-check {
        default_type application/json;
        alias /var/www/project-genesis/db-check.json;
      }
    }
    NGINX

    rm -f /etc/nginx/sites-enabled/default
    ln -sf /etc/nginx/sites-available/project-genesis /etc/nginx/sites-enabled/project-genesis
    nginx -t
    systemctl enable nginx
    systemctl restart nginx

    # Keep local evidence on the instance for optional troubleshooting.
    echo "$DB_JSON" > /var/log/project-genesis-db-check.log

    exit 0
  EOT

  depends_on = [aws_db_instance.genesis]

  tags = {
    Name = "project-genesis-api"
  }
}

output "ec2_public_ip" {
  value = aws_instance.genesis_api.public_ip
}

output "api_health_url" {
  value = "http://${aws_instance.genesis_api.public_ip}/api/v1/health"
}

output "db_check_url" {
  value = "http://${aws_instance.genesis_api.public_ip}/api/v1/db-check"
}
