import boto3

Ec2=boto3.client("ec2","us-east-1")
response=Ec2.describe_instances()
print("Connection successful")
print(response)
