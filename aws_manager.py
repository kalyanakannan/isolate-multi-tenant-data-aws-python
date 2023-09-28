from django.template import Template, Context
import boto3
from feedback.settings import AWS_STORAGE_BUCKET_NAME, PUBLIC_TENANT_ID
from datetime import datetime
from dateutil.tz import tzutc
import pandas as pd

class S3PolicyGenerator:
    _instance = None

    def __new__(cls, tenant_id=None, refresh=False):
        if cls._instance is None or refresh:
            cls._instance = super(S3PolicyGenerator, cls).__new__(cls)
            cls._instance.s3_bucket_name = AWS_STORAGE_BUCKET_NAME
            cls._instance.tenant_id = tenant_id
            cls._instance.public_tenant_id = PUBLIC_TENANT_ID
            cls._instance.update_tenant_key()
            cls._instance.policy_template_name = 's3_tenant_policy.json'
            cls._instance.scopedPolicy = None
            cls._instance.tenant_credentials = None
            cls._instance.role_arn = 'arn:aws:iam::<account-id>:role/s3-read-only-role'
            cls._instance.session = None
            cls._instance.token_expired = True
        return cls._instance

    def update_tenant_key(self):
        self.tenant_key = f"customer-data/tenant={self.tenant_id}"
        self.public_tenant_key = f"customer-data/tenant={self.public_tenant_id}"

    def tenant(self, tenant_id):
        self.tenant_id = tenant_id
        self.update_tenant_key()
        return self

    def get_manage_policy(self):
        s3_client = boto3.client('s3')
        try:
            response = s3_client.get_object(
                Bucket='<managed-policies-bucket>', Key=self.policy_template_name)
            policy = response['Body'].read().decode('utf-8')
            return policy
        except boto3.exceptions.Boto3Error as e:
            print(f"Error retrieving manage policy: {str(e)}")
            return ''
    
    def get_public_policy(self):
        context = {
                'bucket': self.s3_bucket_name,
                'tenant': self.public_tenant_key
            }
        manage_policy = self.get_manage_policy()
        if manage_policy:
            return self.render_policy_template(manage_policy, context)
        return None

    def get_tenant_policy(self, with_public=False):
        public_policy = self.get_public_policy() if with_public else ''
        context = {
            'bucket': self.s3_bucket_name,
            'tenant': self.tenant_key
        }
        tenant_policy = self.render_policy_template(self.get_manage_policy(), context)
        if with_public:
            self.scopedPolicy = f"{{\"Version\": \"2012-10-17\",\"Statement\": [{tenant_policy}, {public_policy}]}}"
        else:
            self.scopedPolicy = f"{{\"Version\": \"2012-10-17\",\"Statement\": [{tenant_policy}]}}"
        print(self.scopedPolicy)
        return self
    
    def render_policy_template(self, policy_template, context):
        return Template(policy_template).render(Context(context))

    def assume_role(self):
        sts_client = boto3.client('sts')
        try:
            assumed_role_object = sts_client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName=f"tenant_{self.tenant_id}",
                Policy=self.scopedPolicy
            )
            self.tenant_credentials=assumed_role_object['Credentials']
        except boto3.exceptions.Boto3Error as e:
            print(f"Error assuming role: {str(e)}")
        return self
    
    def is_token_expired(self):
        expiration_time = self.tenant_credentials['Expiration']
        current_time = datetime.now(tzutc())
        time_until_expiration = (expiration_time - current_time).total_seconds() / 60  # Convert to minutes

        if time_until_expiration <= 30:
            return True
        else:
            return False

    def get_session(self):
        if self.session and not self.is_token_expired():
            return self.session
        self.session = boto3.Session(
            aws_access_key_id=self.tenant_credentials['AccessKeyId'],
            aws_secret_access_key=self.tenant_credentials['SecretAccessKey'],
            aws_session_token=self.tenant_credentials['SessionToken']
        )
        return self.session
    
    def get_role_session(self, with_public=False):
        return self.get_tenant_policy(with_public=with_public).assume_role().get_session()
    
    def test_asssume_role(self):
        s3 = self.session.resource('s3')
        bucket = s3.Bucket(self.s3_bucket_name)
        path = f"customer-data/tenant=2/"
        for obj in bucket.objects.filter(Prefix=path):
            print(obj.key)
    

    
