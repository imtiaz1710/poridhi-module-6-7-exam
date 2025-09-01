"""An AWS Python Pulumi program"""
import pulumi
import pulumi_aws as aws

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


public_security_group = aws.ec2.SecurityGroup("bastion-sg",
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

pulumi.export("public_sg_id", public_security_group.id)


# Use the specified Ubuntu 24.04 LTS AMI
ami_id = 'ami-0933f1385008d33c4'

# Create an EC2 instance in the public subnet
public_instance = aws.ec2.Instance("public-instance",
    instance_type="t2.micro",
    vpc_security_group_ids=[public_security_group.id],
    ami=ami_id,
    subnet_id=public_subnet.id,
    key_name="MyKeyPair",
    associate_public_ip_address=True,
    tags= {
    "Name":  "public-ec2"
    }
)