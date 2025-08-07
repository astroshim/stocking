# from app.extensions import db
#
# class BaseRepository:
#     def __init__(self, session=None):
#         self.session = session or db.session
#
#     def add(self, entity):
#         """세션에 엔티티 추가 (commit 없음)"""
#         self.session.add(entity)
#         return entity
#
#     def delete(self, entity):
#         """세션에서 엔티티 삭제 (commit 없음)"""
#         self.session.delete(entity)
#


from sqlalchemy.orm import Session

class BaseRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, entity):
        """세션에 엔티티 추가 (commit 없음)"""
        self.session.add(entity)
        return entity

    def delete(self, entity):
        """세션에서 엔티티 삭제 (commit 없음)"""
        self.session.delete(entity)