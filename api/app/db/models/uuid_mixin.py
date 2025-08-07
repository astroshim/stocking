import uuid
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy import Column

class UUIDMixin:
    id = Column(CHAR(36), primary_key=True)

    @staticmethod
    def generate_uuid():
        return str(uuid.uuid4())

    def __init__(self, *args, **kwargs):
        if 'id' not in kwargs:
            kwargs['id'] = self.generate_uuid()
        super(UUIDMixin, self).__init__(*args, **kwargs)

