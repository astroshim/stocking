import boto3
from botocore.config import Config
from botocore.exceptions import NoCredentialsError
import uuid
from typing import Dict, List, Optional
from app.config import config as stocking_config


class S3Service:
    def __init__(
            self,
            region_name: str = 'ap-northeast-2',
            environment: str = 'production'
    ):
        self.region_name = region_name
        self.bucket_name = stocking_config.STORAGE_BUCKET_NAME
        self.storage_domain = stocking_config.STORAGE_DOMAIN

        if environment == 'local':
            self.session = boto3.session.Session(profile_name='stocking-profile')
            self.s3_client = self.session.client('s3', config=Config(region_name=self.region_name))
        else:
            self.s3_client = boto3.client('s3',
                                          aws_access_key_id=stocking_config.AWS_ACCESS_KEY_ID,
                                          aws_secret_access_key=stocking_config.AWS_SECRET_ACCESS_KEY,
                                          config=Config(region_name=self.region_name))

    def generate_presigned_url(self, dir: str, file_extension: str = "", expiration: int = 300) -> Dict[str, str]:
        file_name = f"{dir}/{uuid.uuid4()}.{file_extension}"
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_name,
                },
                ExpiresIn=expiration
            )
            return {
                "upload_url": presigned_url,
                "download_url": f"{self.storage_domain}/{file_name}"
            }

        except NoCredentialsError:
            raise Exception("AWS credentials not available")

    def upload_file(self, file_path: str, file_name: Optional[str] = None) -> str:
        """Upload a file to S3"""
        if file_name is None:
            file_name = file_path.split('/')[-1]
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, file_name)
            return f"File uploaded successfully: {file_name}"
        except FileNotFoundError:
            raise Exception(f"The file {file_path} was not found")
        except NoCredentialsError:
            raise Exception("AWS credentials not available")

    def download_file(self, file_name: str, local_path: str) -> str:
        """Download a file from S3"""
        try:
            self.s3_client.download_file(self.bucket_name, file_name, local_path)
            return f"File downloaded successfully: {local_path}"
        except NoCredentialsError:
            raise Exception("AWS credentials not available")
        except self.s3_client.exceptions.NoSuchKey:
            raise Exception(f"The file {file_name} does not exist in the bucket")

    def delete_file(self, file_name: str) -> str:
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_name)
            return f"File deleted successfully: {file_name}"
        except NoCredentialsError:
            raise Exception("AWS credentials not available")

    def list_files(self, prefix: str = "") -> List[str]:
        """List files in the S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except NoCredentialsError:
            raise Exception("AWS credentials not available")
